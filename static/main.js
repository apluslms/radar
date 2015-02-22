/**
 * Toolbox object for the service.
 * 
 */
function JS() {
	this.element = $("#js");
}

JS.prototype.log = function(msg) {
	this.element.append(msg + "\n");
};

JS.prototype.getJSON = function(element, success, fail) {
	var url = element.attr("data-url");
	this.log("Getting JSON from " + url + "...");
	$.getJSON(url, function(data) {
		if (data.length > 0) {
			success(data);
		} else {
			fail();
		}
	});
};
JS.prototype.parseJSON = function(element) {
	var text = element.text().trim();
	if (text.length > 0) {
		return $.parseJSON(text);
	}
	return [];
}

JS.prototype.buildHeat = function(similarity) {
	var m = similarity.length > 0 ? Math.max(d3.median(similarity), 0.01) : 0.01;
	this.median = m;
	this.log("Similarity median " + this.median);
	this.heatMap = [1.4, 1.3, 1.2].map(function (e) { return e * m; });
	this.log("Heat map " + this.heatMap);
};
JS.prototype.heat = function(value) {
	var i = 0;
	while (i < this.heatMap.length) {
		if (value >= this.heatMap[i]) {
			break;
		}
		i++;
	}
	return "heat-" + (i+1);
};

JS.prototype.zero = function(value) {
	return value < 10 ? '0' + value : value;	
};
JS.prototype.date = function(dateText) {
	var date = new Date(dateText);
	return this.zero(date.getDate()) + '.' + this.zero(date.getMonth()) + '. '
	+ this.zero(date.getHours()) + ':' + this.zero(date.getMinutes());
};

JS.prototype.submission = function(submission, review, similarity) {
	var html = "";
	if (review != "default") {
		html += ' <span class="label label-' + review + '"><span class="glyphicon glyphicon-eye-open"></span></span>';
	}
	html += '<small>' + this.date(submission.created)
		+ ' grd: ' + (submission.grade * 100).toFixed(0) + '% len: '
		+ submission.length + '</small>';
	if (similarity != undefined) {
		return '<span class="similarity">' + (similarity * 100).toFixed(0)
			+ '%</span> <span class="key">' + submission.student + '</span>' + html;
	}
	return '<strong class="key">' + submission.student + '</strong>' + html;
};
JS.prototype.tdSubmission = function(comparison, submission, id, url, first) {
	return '<td data-student="' + submission.student + '" data-id="' + id
		+ '" class="' + this.heat(comparison.similarity) + ' ' + comparison.review + '"><a href="' + url + '">'
		+ this.submission(submission, comparison.review, (first != undefined) ? undefined : comparison.similarity) + '</a></td>';
};
JS.prototype.tableSubmissions = function(element, columns, accessRowId) {
	var js = this;
	this.getJSON(element, function(comparisons) {
		js.log("Generating table.");
		for (var i in comparisons) {
			var tr = element.find("tr#" + accessRowId(comparisons[i].a) + ", tr#" + accessRowId(comparisons[i].b));
			if (tr.size() == 0) {
				tr = $('<tr id="' + accessRowId(comparisons[i].a) + '">'
					+ js.tdSubmission(comparisons[i], comparisons[i].a, "", comparisons[i].url, true) + '</tr>');
				element.append(tr);
			}
			if (tr.find("td").size() < columns) {
				var id = comparisons[i].a.id + "-" + comparisons[i].b.id;
				var reverse = (tr.attr("id") == accessRowId(comparisons[i].a)) ? "" : "?reverse";
				var s = (reverse.length > 0) ? comparisons[i].a : comparisons[i].b;
				if (tr.find('td[data-student="' + s.student + '"]').size() == 0) {
					tr.append(js.tdSubmission(comparisons[i], s, id, comparisons[i].url + reverse));
				}
			}
		}
		var selected = element.attr("data-selected");
		if (selected != undefined) {
			element.find('td[data-id="' + selected + '"]').addClass("selected");
		}
	}, function() {
		element.append("<tr><td>0 comparisons</td></tr>");
	});
};

JS.prototype.quickReview = function(element) {
	var key = element.find("button").val();
	var a = element.find('a[data-review="' + key + '"]');
	if (a.size() > 0) {
		this.quickReviewShow(element, a);
	}
	var js = this;
	element.find("a").bind("click", function(event) {
		event.preventDefault();
		var a = $(this);
		var data = {
			"csrfmiddlewaretoken": element.find('input[name="csrfmiddlewaretoken"]').val(),
			"review": parseInt(a.attr("data-review"))
		};
		$.post(element.attr("action"), data, function(res) {
			if (res.success) {
				js.log("Review stored.");
				js.quickReviewShow(a.closest(".btn-group"), a);
			}
		}, "json");
	});
};
JS.prototype.quickReviewShow = function(element, a) {
	element.find("button").removeClass("btn-default btn-primary btn-success btn-info btn-warning btn-danger")
	.addClass("btn-" + a.attr("data-class")).val(a.attr("data-review")).find(".text").text(a.text());
};
