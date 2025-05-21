# Imports
import re
from playwright.sync_api import Page, expect
from random import randrange
from e2e_tests.helpers import login, save_and_navigate_back, change_value


# Test login
def test_login(page: Page) -> None:
    login(page)
    expect(page.get_by_role('button', name='Logout')).to_be_visible()


# Test logout
def test_logout(page: Page) -> None:
    login(page)
    page.get_by_role('button', name='Logout').click()
    expect(page.get_by_text('Username')).to_be_visible()
    expect(page.get_by_text('Password')).to_be_visible()


# Test change exercise name
def test_change_exercise_name(page: Page) -> None:
    exercise_num = randrange(9) + 1
    login(page)
    current_exercise_name = page.locator('td > a').first.inner_text()
    change_value(page, 'Name', f'exercise{exercise_num}')
    change_value(page, 'Name', f'{current_exercise_name}')


# Test change exercise tokenizer
def test_change_tokenizer(page: Page) -> None:
    tokenizers = [
        ("skip", "Skip"),
        ("scala", "Scala"),
        ("python", "Python"),
        ("js", "JavaScript (ECMA 2016)"),
        ("html", "HTML5"),
        ("css", "CSS"),
    ]

    login(page)
    page.get_by_role('link', name=' Settings').first.click()

    current_tokenizer = page.locator('#id_tokenizer').input_value()
    current_tokenizer_index = [x for x, y in enumerate(tokenizers) if y[0] == current_tokenizer][0]
    new_tokenizer_index = randrange(len(tokenizers))
    while current_tokenizer_index == new_tokenizer_index:
        new_tokenizer_index = randrange(len(tokenizers))

    page.get_by_label('Tokenizer type').select_option(index=new_tokenizer_index)
    save_and_navigate_back(page)
    expect(page.locator('tbody')).to_contain_text(tokenizers[new_tokenizer_index][1])
    page.get_by_role('link', name=' Settings').first.click()
    page.get_by_label('Tokenizer type').select_option(index=current_tokenizer_index)
    save_and_navigate_back(page)
    expect(page.locator('tbody')).to_contain_text(tokenizers[current_tokenizer_index][1])


# Test change exercise minimum match tokens
def test_change_minimum_match_tokens(page: Page) -> None:
    min_tokens = randrange(8) + 3
    login(page)
    current_min_tokens = int(page.locator('tr > td:nth-child(9)').first.inner_text().split(' ')[0])
    change_value(page, 'Minimum match tokens', f'{min_tokens}')
    change_value(page, 'Minimum match tokens', f'{current_min_tokens}', ' tokens')


# Test visibility of histogram and grid
def test_similarity_visibility(page: Page) -> None:
    login(page)
    page.locator('td > a').first.click()
    expect(page.get_by_role('img')).to_contain_text(re.compile(r'.+0.00.10.20.30.40.50.60.70.80.91.0'))
    expect(page.locator('.comparison-grid')).to_be_visible()


# Test visibility of exercise histogram
def test_histogram_visibility(page: Page) -> None:
    login(page)
    page.get_by_role('link', name=' Exercise histograms').click()
    expect(page.get_by_role('img').first).to_contain_text(re.compile(r'.+0.00.10.20.30.40.50.60.70.80.91.0'))


# Test visibility of graph view
def test_graph_view(page: Page) -> None:
    login(page)
    page.get_by_role('link', name=' Graph view').click()
    page.get_by_role('button', name='Build graph').click()
    page.locator("svg > line").last.click()
    expect(page.locator('#pair-comparisons-summary-modal')).to_contain_text(
        re.compile(r'.+ and .+ have .+ submission pair.? with high similarity')
    )


# Test visibility of cluster view
def test_cluster_view(page: Page) -> None:
    login(page)
    page.get_by_role('link', name=' Clusters view').click()
    page.get_by_role("button", name="Build table").click()
    page.get_by_role("link", name="Cluster 1").click()
    expect(page.get_by_role("heading", name="Hide Students")).to_be_visible()


# Test visibility of student view
def test_student_view(page: Page) -> None:
    login(page)
    page.get_by_role('link', name=' Students view').click()
    page.locator('.dt-left > a').first.click()
    expect(page.locator('.content.container-fluid > p').first).to_contain_text(
        re.compile(r'All comparisons for .+ with similarity greater than .+%')
    )


# Test visibility of flagged pairs
def test_flagged_pairs(page: Page) -> None:
    login(page)
    page.locator('td > a').first.click()
    page.get_by_role('link', name=re.compile(r'.+% .+ vs .+')).first.click()
    page.locator('[name="review"]').click()
    page.get_by_role('link', name='Plagiate', exact=True).click()
    page.locator('.breadcrumb > li:nth-child(2)').click()
    page.get_by_role('link', name=' Flagged pairs').click()
    page.get_by_role('link', name=re.compile(r'.+ vs .+')).click()
    page.get_by_role('link', name='Get summary of marked').click()
    expect(page.get_by_role('heading')).to_contain_text('Similarity Summary')
    page.locator('.breadcrumb > li:nth-child(2)').click()
    page.locator('td > a').first.click()
    page.get_by_role('link', name=re.compile(r'.+% .+ vs .+')).first.click()
    page.locator('[name="review"]').click()
    page.get_by_role('link', name='Unspecified match', exact=True).click()
