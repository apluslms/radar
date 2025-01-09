# Imports
from playwright.sync_api import Page, expect

# Function to login
def login(page: Page) -> None:
    page.goto('http://localhost:8000/')
    page.get_by_label('Username').click()
    page.get_by_label('Username').fill('Username')
    page.get_by_label('Password').click()
    page.get_by_label('Password').fill('Password')
    page.get_by_role('link', name='Hide »').click()
    page.get_by_role('button', name='Login').click()
    page.locator('td > a').first.click()

# Function to save settings and navigate back
def save_and_navigate_back(page: Page) -> None:
    page.locator('button[name=\'save\']').click()
    page.locator('.breadcrumb > li:nth-child(2)').click()

#Function to change exercise value and check if it was changed
def change_value(page: Page, value_to_change: str, exercise_value: str, contain_text: str = '') -> None:
    page.get_by_role('link', name=' Settings').first.click()
    page.get_by_label(value_to_change).click()
    page.get_by_label(value_to_change).fill(exercise_value)
    save_and_navigate_back(page)
    expect(page.locator('tbody')).to_contain_text(f'{exercise_value}{contain_text}')
