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
	
	var as = codePre.find("a.match").bind("mouseenter", _codeviewEnter)
		.bind("mouseleave", _codeviewLeave)
		.bind("click", _codeviewClick);
	codePre.scrollTop(as.filter(".compared").eq(0).position().top - 30);
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
	if (last < code.length) {
		result += code.substring(last, code.length);
	}
	return "<span class=\"source\">" + result + "</span>";
}

function _codeviewMatchWrap(code, m) {
	classes = "match";
	if (m["compare"]) {
		classes += " compared";
	}
	return "<a class=\"" + classes + "\" data-id=\"" + m["group"]+ "\" href=\"#\">"
		+ code.substring(m["first"], m["last"] + 1) + "</a>";
}

function _codeviewEnter(event) {
	var id = $(this).attr("data-id");
	$("pre.codeview a[data-id=\"" + id + "\"]").addClass("current");
}

function _codeviewLeave(event) {
	var id = $(this).attr("data-id");
	$("pre.codeview a[data-id=\"" + id + "\"]").removeClass("current");
}

function _codeviewClick(event) {
	event.preventDefault();
}
