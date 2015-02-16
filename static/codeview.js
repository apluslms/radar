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
	return "<span class=\"source\">" + result + "</span>";
}

function _codeviewMatchWrap(code, m) {
	classes = "match";
	if (m["compare"]) {
		classes += " compared";
	}
	return "<a class=\"" + classes + "\" data-id=\"" + m["group"]+ "\" href=\"#\">"
		+ code.substring(m["first"], m["last"]) + "</a>";
}
