JS.prototype.codeview = function(element) {
	this.log("Augmenting comparison view.");
	
	this.codeviewElements = element.find("pre.code-view");
	var left_view = element.find("pre.code-a");
	var right_view = element.find("pre.code-b");
	
	var reverse = element.attr("data-reverse") != undefined;
	var a_code = reverse ? right_view.text() : left_view.text();
	var b_code = reverse ? left_view.text() : right_view.text();
	var a_indexes = this.parseJSON(element.find(reverse ? "pre.indexes-b" : "pre.indexes-a"));
	var b_indexes = this.parseJSON(element.find(reverse ? "pre.indexes-a" : "pre.indexes-b"));
	var a_template = this.parseJSON(element.find(reverse ? "pre.template-b" : "pre.template-a"));
	var b_template = this.parseJSON(element.find(reverse ? "pre.template-a" : "pre.template-b"));
	
	var matches = this.parseJSON(element.find("pre.matches"));
	var matches02 = function(e) { return([ e[0], 0, e[2] ]); };
	var matches12 = function(e) { return([ e[1], 0, e[2] ]); };
	var a_matches = matches.map(reverse ? matches12 : matches02);
	var b_matches = matches.map(reverse ? matches02 : matches12);
	
	this.codeviewAugment(left_view, a_code, a_indexes, a_template, a_matches);
	this.codeviewAugment(right_view, b_code, b_indexes, b_template, b_matches);
	
	this.codeviewFindExact();
	this.codeviewFocus("a.match");
};

JS.prototype.codeviewAugment = function(element, code, indexes, template, matches) {
	element.html(this.codeviewMatched(code, indexes, template, matches));
	hljs.highlightBlock(element[0]);
	var js = this;
	var as = element.find("a.match").bind("mouseenter", function(event) {
		js.codeviewElements.find('a[data-i="' + $(this).attr("data-i") + '"]').addClass("current");
	}).bind("mouseleave", function(event) {
		js.codeviewElements.find('a[data-i="' + $(this).attr("data-i") + '"]').removeClass("current");			
	}).bind("click", function(event) {
		event.preventDefault();
		js.codeviewFocus('a.match[data-i="' + $(this).attr("data-i") + '"]');
	});
};

JS.prototype.codeviewFocus = function(selector) {
	this.codeviewElements.each(function() {
		var view = $(this);
		var children = view.find(selector);
		if (children.size() > 0) {
			view.scrollTop(view.scrollTop() + children.eq(0).position().top - 30);
		}
	});
};

JS.prototype.codeviewMatched = function(code, indexes, template, matches) {
	var result = "";
	var ma = this.codeviewJoinMatches(template, matches, "template");
	var last = 0, b = 0, e = 0;
	for (i in ma) {
		b = indexes[ma[i].beg][0];
		e = indexes[ma[i].end][1] + 1;
		if (b > last) {
			result += code.substring(last, b);
		}
		var anchor = ma[i].first ? '<a class="template">' : '<a class="match" data-i="' + ma[i].index + '" href="#">';
		result += anchor + code.substring(b, e) + '</a>';
		last = e;
	}
	if (last < code.length) {
		result += code.substring(last, code.length);
	}
	return "<span class=\"source\">" + result + "</span>";
};

JS.prototype.codeviewJoinMatches = function(ma1, ma2) {
	var a = [], mi1 = 0, mi2 = 0;
	while (mi1 < ma1.length || mi2 < ma2.length) {
		if (mi1 < ma1.length && (mi2 >= ma2.length || ma1[mi1][0] < ma2[mi2][0])) {
			a.push({ "beg": ma1[mi1][0], "end": ma1[mi1][0] + ma1[mi1][2] - 1, "index": mi1, "first": true });
			mi1++;
		} else {
			a.push({ "beg": ma2[mi2][0], "end": ma2[mi2][0] + ma2[mi2][2] - 1, "index": mi2, "first": false });
			mi2++;
		}
	}
	return a;
};

JS.prototype.codeviewFindExact = function() {
	var right = this.codeviewElements.filter(".code-b");
	this.codeviewElements.filter(".code-a").find("a.match").each(function() {
		var l = $(this);
		var r = right.find('a.match[data-i="' + l.attr("data-id") + '"]');
		if (r.size() > 0 && l.text() == r.eq(0).text()) {
			l.addClass("exact");
			r.addClass("exact");
		}
	});
};
