JS.prototype.codeview = function(element) {
	this.log("Augmenting comparison view.");

	this.codeviewElements = element.find("pre.code-view");
	var left_view = element.find("pre.code-a");
	var right_view = element.find("pre.code-b");

	var reverse = element.attr("data-reverse") != undefined;
	var a_code = left_view.text();
	var b_code = right_view.text();
	var a_indexes = this.parseJSON(element.find("pre.indexes-a"));
	var b_indexes = this.parseJSON(element.find("pre.indexes-b"));
	var a_template = this.parseJSON(element.find("pre.template-a"));
	var b_template = this.parseJSON(element.find("pre.template-b"));

	var matches = this.parseJSON(element.find("pre.matches"));
	var matches02 = function(e) { return([ e[0], 0, e[2] ]); };
	var matches12 = function(e) { return([ e[1], 0, e[2] ]); };
	var a_matches = matches.map(reverse ? matches12 : matches02);
	var b_matches = matches.map(reverse ? matches02 : matches12);

	this.codeviewAugment(left_view, a_code, a_indexes, a_template, a_matches);
	this.codeviewAugment(right_view, b_code, b_indexes, b_template, b_matches, true);

	this.codeviewFindExact();
	this.codeviewFocus("a.match");
};

JS.prototype.codeviewAugment = function(element, code, indexes, template, matches, right=false) {
	element.html(this.codeviewMatched(code, indexes, template, matches, right));
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

JS.prototype.codeviewMatched = function(code, indexes, template, matches, right) {
	var result = "";
	var ma = this.codeviewJoinMatches(template, matches, "template");
	var last = 0, b = 0, e = 0;

  //Check if right side code
  if (right) {
    //Sort array by beginning value of each match
    ma.sort(function(a, b) {
      return a.beg - b.beg;
    });
  }

	for (i in ma) {
    var move = 0;

    //Check if two matches are on the same line. If they are, move the match to the right.
    if (i > 0) {
      move = this.isSameLine(code, indexes[ma[i-1].end][1], indexes[ma[i].beg][0]);
    }

    //Check if two matches are on the same line. If they are, move the match to the right.
    if (i < ma.length - 1) {
      move += this.isSameLine(code, indexes[ma[i].end][1], indexes[ma[parseInt(i)+1].beg][0]);
    }

    //Get the beginning and end index of the match
		b = indexes[ma[i].beg][0] + move;
    e = indexes[ma[i].end][1] + 1 + move;

    //Check if match start should be moved to the start of the line or end of the line.
    if (this.getMidPoint(code, b) > b) {
      b = this.getStartOfLine(code, b);
    } else {
      b = this.getEndOfLine(code, b);
    }

    //Check if match end should be moved to the start of the line or end of the line.
    if (this.getMidPoint(code, e) > e) {
      e = this.getStartOfLine(code, e);
    } else {
      e = this.getEndOfLine(code, e);
    }

		if (b > last) {
			result += this.escape_tags(code.substring(last, b));
		}
		var anchor = ma[i].first ? '<a class="template">' : '<a class="match" data-i="' + ma[i].index + '" href="#">';
		result += anchor + this.escape_tags(code.substring(b, e)) + '</a>';
		last = e;
	}
	if (last < code.length) {
		result += this.escape_tags(code.substring(last, code.length));
	}
	return "<span class=\"source\">" + result + "</span>";
};

// Get end of line index
JS.prototype.getEndOfLine = function(code, start) {
  var output = code.indexOf("\n", start);
  return output;
}

// Get start of line index
JS.prototype.getStartOfLine = function(code, end) {
  var output = code.lastIndexOf("\n", end);
  return output;
}

// Get middle of line index
JS.prototype.getMidPoint = function(code, position) {
  var start = code.lastIndexOf("\n", position);
  var end = code.indexOf("\n", position);
  var output = (end + start)*0.55;
  return output;
}

// Check if two matches are on the same line
JS.prototype.isSameLine = function(code, end, start) {
  var lineStart = code.lastIndexOf("\n", end);
  var lineEnd = code.indexOf("\n", end);

  if (lineStart <= start && lineEnd >= start) {
    var b = lineEnd - start;
    return b;
  } else {
    return 0;
  }
}

JS.prototype.escape_tags = function(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
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
		var r = right.find('a.match[data-i="' + l.attr("data-i") + '"]');
		if (r.size() > 0 && l.text() == r.eq(0).text()) {
			l.addClass("exact");
			r.addClass("exact");
		}
	});
};
