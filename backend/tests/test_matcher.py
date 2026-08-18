"""Tests for the matching logic.

Each test names a specific way the catalog was built to break naive matching,
so a failure points at which property regressed rather than merely that a score
moved.
"""

import pytest

from matching.catalog import load_catalog
from matching.matcher import AUTO, REVIEW, UNMATCHED, match_spine


@pytest.fixture(scope='module')
def catalog():
    return load_catalog()


def best_id(result):
    return result.best.entry.id if result.best else None


def test_clean_read_is_accepted_without_asking(catalog):
    result = match_spine('The Great Gatsby', 'F. Scott Fitzgerald', catalog)

    assert best_id(result) == '80'
    assert result.status == AUTO


def test_ocr_noise_still_reaches_the_right_book(catalog):
    """A spine photographed at an angle loses characters but stays matchable."""
    result = match_spine('Hary Poter and the Philosphers Ston', 'J.K. Rowling', catalog)

    assert best_id(result) == '8'


def test_author_in_lastname_firstname_order(catalog):
    result = match_spine('The Hobbit', 'Tolkien, J. R. R.', catalog)

    assert result.best.entry.title == 'The Hobbit'
    assert result.best.author_similarity >= 0.85


def test_author_read_without_accents(catalog):
    """Spine reads arrive unaccented; the catalog records the accented form."""
    result = match_spine('One Hundred Years of Solitude', 'Gabriel Garcia Marquez', catalog)

    assert best_id(result) == '63'
    assert result.status == AUTO


def test_transliterated_author_matches(catalog):
    result = match_spine('Crime and Punishment', 'Dostoyevsky', catalog)

    assert best_id(result) == '59'


def test_shared_title_without_author_is_not_auto_accepted(catalog):
    """Two different books are called The Alchemist, so the title alone cannot decide."""
    result = match_spine('The Alchemist', None, catalog)

    assert result.status == REVIEW
    assert result.confidence < 0.85
    assert any('No author' in reason for reason in result.reasons)


def test_shared_title_with_author_is_resolved(catalog):
    """The same read becomes decisive once an author is present."""
    result = match_spine('The Alchemist', 'Paulo Coelho', catalog)

    assert best_id(result) == '40'
    assert result.status == AUTO


def test_shared_title_picks_the_right_author(catalog):
    result = match_spine('Inferno', 'Dan Brown', catalog)

    assert best_id(result) == '68'

    other = match_spine('Inferno', 'Dante Alighieri', catalog)
    assert best_id(other) == '27'


def test_substring_title_does_not_capture_the_shorter_entry(catalog):
    """Reading 'It' must not resolve to 'It Ends with Us'."""
    result = match_spine('It', 'Stephen King', catalog)

    assert best_id(result) == '42'


def test_longer_title_is_not_captured_by_its_substring(catalog):
    """The same error from the other side: 'It Ends with Us' is not 'It'."""
    result = match_spine('It Ends with Us', 'Colleen Hoover', catalog)

    assert best_id(result) == '44'


def test_substring_of_a_longer_title(catalog):
    result = match_spine('The Road', 'Cormac McCarthy', catalog)

    assert best_id(result) == '38'
    assert result.best.entry.title == 'The Road'


def test_us_uk_retitling_reaches_the_work(catalog):
    """A UK spine matches the work even though the catalog splits it in two."""
    result = match_spine("Harry Potter and the Philosopher's Stone", 'J. K. Rowling', catalog)

    assert result.best.entry.title in {
        "Harry Potter and the Philosopher's Stone",
        'Harry Potter and the Sorcerer’s Stone',
        'Harry Potter and the Sorcerer\'s Stone',
    }
    assert best_id(result) == '8'


def test_two_editions_of_one_work_are_ambiguous(catalog):
    """Nothing on a spine distinguishes the 1937 Hobbit from the 2012 reissue."""
    result = match_spine('The Hobbit', 'J. R. R. Tolkien', catalog)

    assert result.status == REVIEW
    assert {c.entry.id for c in result.candidates} >= {'1', '2'}


def test_omnibus_does_not_swallow_its_volume(catalog):
    result = match_spine('The Fellowship of the Ring', 'J. R. R. Tolkien', catalog)

    assert best_id(result) == '4'


def test_visually_confusable_titles_stay_apart(catalog):
    assert best_id(match_spine('1984', 'George Orwell', catalog)) == '34'
    assert best_id(match_spine('1Q84', 'Haruki Murakami', catalog)) == '67'


def test_ampersand_and_hyphen_variants(catalog):
    assert best_id(match_spine('Angels & Demons', 'Dan Brown', catalog)) == '70'
    assert best_id(match_spine('Catch 22', 'Joseph Heller', catalog)) == '86'


def test_leading_article_difference_is_forgiven(catalog):
    result = match_spine('The Joy of Cooking', 'Irma Rombauer', catalog)

    assert best_id(result) == '142'


def test_book_absent_from_the_catalog_is_reported_unmatched(catalog):
    result = match_spine('Advanced Marine Boiler Maintenance', 'K. Oduya', catalog)

    assert result.status == UNMATCHED
    assert result.candidates == ()


def test_unreadable_spine_is_reported_not_dropped(catalog):
    """A spine the model could not read still produces a result object."""
    result = match_spine('', None, catalog)

    assert result.status == UNMATCHED
    assert result.reasons


def test_ambiguous_result_explains_the_runner_up(catalog):
    """A review prompt has to say what the doubt is to be answerable."""
    result = match_spine('The Girl on the Train', None, catalog)

    assert result.status == REVIEW
    assert any('scored almost as highly' in reason for reason in result.reasons)


def test_confidence_is_bounded(catalog):
    for title, author in [
        ('The Great Gatsby', 'F. Scott Fitzgerald'),
        ('It', None),
        ('nonsense text', 'nobody'),
    ]:
        result = match_spine(title, author, catalog)
        assert 0.0 <= result.confidence <= 1.0
