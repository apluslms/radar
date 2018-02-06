import datetime
from functools import reduce
from urllib.parse import urlsplit
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _


class ApiNamespace(models.Model):
    domain = models.CharField(max_length=255, db_index=True)

    class Meta:
        abstract = not any((x in settings.INSTALLED_APPS for x in ('aplus_client', 'aplus_client.django')))
        verbose_name = _("Namespace")
        verbose_name_plural = _("Namespaces")

    @classmethod
    def get_by_url(cls, url):
        hostname = urlsplit(url).hostname
        if not hostname:
            raise ValueError("Url doesn't have hostname")
        obj, created = cls.objects.get_or_create(domain=hostname)
        return obj

    def __str__(self):
        return self.domain


class CachedApiQuerySet(models.QuerySet):
    def get_new_or_updated(self, api_obj, **kwargs):
        obj, created = self.get_or_create(api_obj, **kwargs)
        if not created and obj.should_be_updated:
            self.update_object(obj, api_obj, **kwargs)
            obj.save()
        return obj

    def get_or_create(self, api_obj, **kwargs):
        select_related = kwargs.pop('select_related', None)
        try:
            qs = self
            if select_related:
                qs = qs.select_related(*select_related)
            return qs.get(api_id=api_obj.id, **kwargs), False
        except ObjectDoesNotExist:
            return self.create(api_obj, **kwargs), True

    def create(self, api_obj, **kwargs):
        obj = self.model(api_id=api_obj.id)
        self.update_object(obj, api_obj, **kwargs)
        obj.save()
        return obj

    def update_object(self, obj, api_obj, **kwargs):
        if not obj.url and api_obj.url:
            obj.url = api_obj.url
        obj.update_with(api_obj, **kwargs)

    update_object.queryset_only = True


CachedApiManager = models.Manager.from_queryset(CachedApiQuerySet)


class CachedApiObject(models.Model):
    TTL = datetime.timedelta(hours=1)

    class Meta:
        abstract = True
        get_latest_by = 'updated'

    api_id = models.IntegerField()
    url = models.URLField()
    updated = models.DateTimeField(auto_now=True)

    @property
    def should_be_updated(self):
        age = timezone.now() - self.updated
        return age > self.TTL

    def update_using(self, client):
        data = client.load_data(self.url)
        self.update_with(data)

    def update_with(self, api_obj, **kwargs):
        fields = (
            (f, f.name, f.related_model)
            for f in self._meta.get_fields()
            if (
                f.concrete and (
                    not f.is_relation
                    or f.one_to_one
                    or (f.many_to_one and f.related_model)
                ) and
                f.name not in ('id', 'url', 'updated')
            )
        )
        for f, name, model in fields:
            if name in kwargs:
                setattr(self, name, kwargs[name])
                continue
            try:
                value = api_obj[name]
            except KeyError:
                continue
            if model:
                value = model.objects.get_new_or_updated(value, **kwargs)
            setattr(self, name, value)


class NamespacedApiQuerySet(CachedApiQuerySet):
    def using_namespace(self, namespace):
        if not isinstance(namespace, ApiNamespace):
            namespace = ApiNamespace.get_by_url(namespace)
        return self.filter(namespace=namespace)

    def using_namespace_id(self, namespace_id):
        return self.filter(namespace_id=namespace_id)

    def get_new_or_updated(self, api_obj, **kwargs):
        if 'namespace' not in kwargs:
            kwargs['namespace'] = ApiNamespace.get_by_url(api_obj.url)
        return super().get_new_or_updated(api_obj, **kwargs)

    def update_object(self, obj, api_obj, namespace=None, **kwargs):
        if namespace is None:
            try:
                namespace = obj.namespace
            except ObjectDoesNotExist:
                namespace = ApiNamespace.get_by_url(api_obj.url)
        try:
            obj.namespace
        except ObjectDoesNotExist:
            obj.namespace = namespace
        super().update_object(obj, api_obj, namespace=namespace, **kwargs)


class NamespacedApiObject(CachedApiObject):
    Manager = CachedApiManager.from_queryset(NamespacedApiQuerySet)
    objects = Manager()

    namespace = models.ForeignKey(ApiNamespace, on_delete=models.PROTECT)

    class Meta:
        abstract = True
        unique_together = ('namespace', 'api_id')

    def update_with(self, api_obj, **kwargs):
        kwargs.setdefault('namespace', self.namespace)
        super().update_with(api_obj, **kwargs)


class NestedApiQuerySet(CachedApiQuerySet):
    @cached_property
    def namespace_filter(self):
        return self.model.NAMESPACE_FILTER

    def filter(self, *args, **kwargs):
        if 'namespace' in kwargs:
            kwargs[self.namespace_filter] = kwargs.pop('namespace')
        return super().filter(*args, **kwargs)

    def get_new_or_updated(self, api_obj, **kwargs):
        if 'namespace' not in kwargs:
            kwargs['namespace'] = ApiNamespace.get_by_url(api_obj.url)
        return super().get_new_or_updated(api_obj, **kwargs)


class NestedApiObject(CachedApiObject):
    NAMESPACE_FILTER = None

    Manager = CachedApiManager.from_queryset(NestedApiQuerySet)
    objects = Manager()

    class Meta:
        abstract = True

    @property
    def namespace(self):
        raise NotImplementedError("Subclass should define .namespace property")
