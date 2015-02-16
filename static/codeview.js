/**
 * Highlight and prettify code views.
 */
function codeview(codeSelector, matchSelector) {
	
	var codePre = $(codeSelector);
	if (codePre.size() != 1) {
		return false;
	}

	var matchPre = $(matchSelector);
	if (matchPre.size() == 1) {
		var text = matchPre.text().trim();
		if (text != "") {
			var json = $.parseJSON(text);
			codePre.html(_codeviewMatches(codePre.text(), json));
		}
	}
	
	hljs.highlightBlock(codePre[0]);
	
	return true;
}

function _codeviewMatches(code, matches) {
	result = "";
	var last = 0;
	var m = null;
	for (i in matches) {
		m = matches[i];
		if (m["first"] > last) {
			result += code.substring(last, m["first"]);
		}
		result += _codeviewMatchWrap(code, m);
		last = m["last"] + 1
	}
	return result;
}

function _codeviewMatchWrap(code, m) {
	return "<a class=\"match\" data-id=\"" + m["group"]+ "\">"
		+ code.substring(m["first"], m["last"]) + "</a>";
}

/**
 * Highlights elements between two comments.
 */
function _codeviewHighlight(beginComment, endComment, style) {
	var beg = '/* ' + beginComment + ':';
	var end = '/* ' + endComment + ':';

	// Find the limits.
	var b = this.element.find('span:contains(' + beg + ')').addClass(
			"limit").addClass("highlighter");
	var e = this.element.find('span:contains(' + end + ')').addClass(
			"limit").addClass("highlighter");

	// Highlight the start and stop lines.
	b.nextUntil(".limit").addClass(style);
	e.prevUntil(".limit").addClass(style);
	b.removeClass("limit");
	e.removeClass("limit");

	// Highlight lines between.
	e.each(function(index) {
		var span = $(this);
		var t = span.text();
		var i = parseInt(t.substring(t.indexOf(end) + end.length));
		span.parent("li").addClass("stop-" + i);
	});
	b.each(function(index) {
		var span = $(this);
		var t = span.text();
		var i = parseInt(t.substring(t.indexOf(beg) + beg.length));
		var li = span.parent("li");
		var stop = "stop-" + i;
		if (li.hasClass(stop)) {
			li.removeClass(stop);
		} else {
			li.nextUntil('.' + stop).children().addClass(style);
			li.nextAll('.' + stop).removeClass(stop);
		}
	});
}


	/**
	 * Constructs a code view.
	 *
	function CodeView(jQueryElement, callback) {
		this.element = jQueryElement;
		this.callback = callback;
	}
	$.extend(CodeView.prototype, {

		/**
		 * Resets the view.
		 *
		reset : function(language) {
			this.element.find("#targetcode, #sourcecode").remove();
			this.element.append(this.codeElement("targetcode", language)
					+ this.codeElement("sourcecode", language));
			this.target = this.element.find("#targetcode");
			this.source = this.element.find("#sourcecode");
			this.targetReceived = false;
			this.sourceReceived = false;
		},

		/**
		 * Creates code view HTML.
		 *
		codeElement : function(id, language) {
			return '<pre id="' + id + '" class="prettyprint linenums lang-'
					+ language + '"></pre>';
		},

		/**
		 * Sets target code.
		 *
		setTarget : function(code, templateMatches, matches, index) {
			this.targetCode = code;
			this.targetTpl = templateMatches;
			this.targetReceived = true;
			this.finish(matches, index);
		},

		/**
		 * Sets source code.
		 *
		setSource : function(code, templateMatches, matches, index) {
			this.sourceCode = code;
			this.sourceTpl = templateMatches;
			this.sourceReceived = true;
			this.finish(matches, index);
		},

		/**
		 * Finishes the source code views.
		 *
		finish : function(matches, index) {
			if (this.targetReceived && this.sourceReceived) {
				this.callback();

				// Mark exact matches.
				var path = matches[index]["target_start_path"];
				for ( var i in matches) {
					var m = matches[i];
					if (m.target_start_path != path) {
						continue;
					}
					if (this.targetCode.substring(m.target_start_char,
							m.target_stop_char + 1) == this.sourceCode
							.substring(m.source_start_char,
									m.source_stop_char + 1)) {
						m.exact = true;
					}
				}

				// Add part divider comments to code.
				this.element.find("#targetcode").text(
						this.format(this.targetTpl, matches, index, "target",
								this.targetCode));
				this.element.find("#sourcecode").text(
						this.format(this.sourceTpl, matches, index, "source",
								this.sourceCode));

				// Call google code prettify.
				PR.prettyPrint();

				// Highlight parts.
				this.highlight("PLAGGIE2:exbegin", "PLAGGIE2:exend", "exact");
				this.highlight("PLAGGIE2:begin", "PLAGGIE2:end", "matched");
				this.highlight("PLAGGIE2:tplbegin", "PLAGGIE2:tplend",
						"template");

				// Find anchor comments and scroll to position.
				var tAnchor = this.target
						.find('span:contains(/* PLAGGIE2:anchor *)');
				var sAnchor = this.source
						.find('span:contains(/* PLAGGIE2:anchor *)');
				var hl = this.element.find("span.highlighter").text('');
				this.target.scrollTop(tAnchor.position().top - 30);
				this.source.scrollTop(sAnchor.position().top - 30);

				// Remove highlight comments.
				hl.remove();
			}
		},

	});
*/