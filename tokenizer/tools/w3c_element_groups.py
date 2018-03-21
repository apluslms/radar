import json

import requests
import bs4


W3C_REF_ELEMENTS_BY_FUNCTION = "https://w3c.github.io/html-reference/elements-by-function.html"

def div_section_with_element_spec(tag):
    return (tag.name == "div"
            and tag.has_attr("class")
            and tag["class"] == ["no-toc", "section"])

def span_with_element_name(tag):
    return (tag.name == "span"
            and tag.has_attr("class")
            and tag["class"] == ["element"])

def get_html_elems_by_function():
    """
    Do a GET to W3C_REF_ELEMENTS_BY_FUNCTION and parse sections into a dict containing element group names as keys and a list of element names that belong to that group.
    """
    res = requests.get(W3C_REF_ELEMENTS_BY_FUNCTION)
    res.raise_for_status()
    assert "HTML elements organized by function" in res.text, "Unexpected response text contents"
    soup = bs4.BeautifulSoup(res.text, "html.parser")
    element_group_divs = soup.body.find_all(div_section_with_element_spec)
    return {d['id']: [li.find_all(span_with_element_name)[0].text
                      for li in d.ul.find_all("li")]
            for d in element_group_divs}

if __name__ == "__main__":
    group_to_elements = get_html_elems_by_function()
    print(json.dumps(group_to_elements))
