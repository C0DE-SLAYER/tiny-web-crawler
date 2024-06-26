from unittest.mock import MagicMock, mock_open, patch

import responses

import pytest

from tiny_web_crawler.core.spider import Spider
from tiny_web_crawler.logging import DEBUG
from tests.utils import setup_mock_response

@responses.activate
def test_crawl() -> None:
    setup_mock_response(
        url="http://example.com",
        body="<html><body><a href='http://example.com/test'>link</a></body></html>",
        status=200,
    )
    setup_mock_response(
        url="http://example.com/test",
        body="<html><body><a href='http://example.com'>link</a></body></html>",
        status=200,
    )

    spider = Spider("http://example.com", 10)
    spider.crawl("http://example.com")

    assert "http://example.com" in spider.crawl_result
    assert spider.crawl_result["http://example.com"]["urls"] == [
        "http://example.com/test"
    ]

    spider.crawl("http://example.com/test")

    assert "http://example.com/test" in spider.crawl_result
    assert spider.crawl_result["http://example.com/test"]["urls"] == [
        "http://example.com"
    ]


@responses.activate
def test_crawl_invalid_url(caplog) -> None:  # type: ignore
    spider = Spider("http://example.com")

    with caplog.at_level(DEBUG):
        spider.crawl("invalid_url")

    assert "Invalid url to crawl:" in caplog.text
    assert spider.crawl_result == {}


@responses.activate
def test_crawl_already_crawled_url(caplog) -> None:  # type: ignore
    setup_mock_response(
        url="http://example.com",
        body="<html><body><a href='http://example.com'>link</a></body></html>",
        status=200,
    )

    spider = Spider("http://example.com")

    with caplog.at_level(DEBUG):
        spider.crawl("http://example.com")
        spider.crawl("http://example.com")

    assert "URL already crawled:" in caplog.text
    assert spider.crawl_result == {
        "http://example.com": {"urls": ["http://example.com"]}
    }


@responses.activate
def test_crawl_unfetchable_url() -> None:
    setup_mock_response(
        url="http://example.com",
        body="<html><body><a href='http://example.com'>link</a></body></html>",
        status=404,
    )

    spider = Spider("http://example.com")

    spider.crawl("http://example.com")
    assert spider.crawl_result == {}


@responses.activate
def test_crawl_found_invalid_url(caplog) -> None:  # type: ignore
    setup_mock_response(
        url="http://example.com",
        body="<html><body><a href='^invalidurl^'>link</a></body></html>",
        status=200,
    )

    spider = Spider("http://example.com")

    with caplog.at_level(DEBUG):
        spider.crawl("http://example.com")

    assert "Invalid url:" in caplog.text
    assert spider.crawl_result == {"http://example.com": {"urls": []}}


@responses.activate
def test_crawl_found_duplicate_url() -> None:
    setup_mock_response(
        url="http://example.com",
        body="<html><body><a href='http://duplicate.com'>link1</a>"
        + "<a href='http://duplicate.com'>link2</a></body></html>",
        status=200,
    )

    spider = Spider("http://example.com")
    spider.crawl("http://example.com")

    assert spider.crawl_result == {
        "http://example.com": {"urls": ["http://duplicate.com"]}
    }


@responses.activate
def test_crawl_no_urls_in_page() -> None:
    setup_mock_response(
        url="http://example.com", body="<html><body></body></html>", status=200
    )

    spider = Spider("http/example.com")
    spider.crawl("http://example.com")

    assert spider.crawl_result == {"http://example.com": {"urls": []}}


@responses.activate
def test_save_results() -> None:
    spider = Spider("http://example.com", 10, save_to_file="out.json")
    spider.crawl_result = {"http://example.com": {"urls": ["http://example.com/test"]}}

    with patch("builtins.open", mock_open()) as mocked_file:
        spider.save_results()
        mocked_file.assert_called_once_with("out.json", "w", encoding="utf-8")


@responses.activate
def test_url_regex() -> None:
    setup_mock_response(
        url="http://example.com",
        body="<html><body><a href='http://example.com/123'>link</a>"
        + "<a href='http://example.com/test'>link</a></body></html>",
        status=200,
    )

    # This regex matches strings starting with "http://example.com/"
    # And only have numeric characters after it
    regex = r"http://example\.com/[0-9]+"

    spider = Spider("http://example.com", 0, url_regex=regex)
    spider.start()

    assert spider.crawl_result["http://example.com"]["urls"] == [
        "http://example.com/123"
    ]

    assert (
        "http://example.com/test"
        not in spider.crawl_result["http://example.com"]["urls"]
    )


@responses.activate
def test_include_body() -> None:
    setup_mock_response(
        url="http://example.com",
        body="<html><body><a href='http://example.com/test'>link</a></body></html>",
        status=200,
    )
    setup_mock_response(
        url="http://example.com/test",
        body="<html><body><h>This is a header</h></body></html>",
        status=200,
    )

    spider = Spider("http://example.com", include_body=True)
    spider.start()

    assert (
        spider.crawl_result["http://example.com"]["body"]
        == '<html><body><a href="http://example.com/test">link</a></body></html>'
    )
    assert (
        spider.crawl_result["http://example.com/test"]["body"]
        == "<html><body><h>This is a header</h></body></html>"
    )


@responses.activate
def test_internal_links_only(caplog) -> None: # type: ignore
    setup_mock_response(
        url="http://internal.com",
        body="<html><body><a href='http://internal.com/test'>link</a>"
        +"<a href='http://external.com/test'>link</a></body></html>",
        status=200,
    )

    spider = Spider("http://internal.com", internal_links_only=True)

    with caplog.at_level(DEBUG):
        spider.crawl("http://internal.com")

    assert "Skipping: External link:" in caplog.text
    assert spider.crawl_result == {"http://internal.com": {"urls": ["http://internal.com/test"]}}


@responses.activate
def test_external_links_only(caplog) -> None: # type: ignore
    setup_mock_response(
        url="http://internal.com",
        body="<html><body><a href='http://internal.com/test'>link</a>"
        +"<a href='http://external.com/test'>link</a></body></html>",
        status=200,
    )

    spider = Spider("http://internal.com", external_links_only=True)

    with caplog.at_level(DEBUG):
        spider.crawl("http://internal.com")

    assert "Skipping: Internal link:" in caplog.text
    assert spider.crawl_result == {"http://internal.com": {"urls": ["http://external.com/test"]}}


@responses.activate
def test_external_and_internal_links_only() -> None:
    with pytest.raises(ValueError):
        Spider("http://example.com", external_links_only=True, internal_links_only=True)


@patch.object(Spider, "crawl")
@patch.object(Spider, "save_results")
def test_start(mock_save_results: MagicMock, mock_crawl: MagicMock) -> None:
    spider = Spider("http://example.com", 10)
    mock_crawl.side_effect = lambda url: spider.crawl_result.update(
        {url: {"urls": ["http://example.com/test"]}}
    )
    print(mock_save_results)

    spider.start()

    assert mock_crawl.call_count == 1
    assert "http://example.com" in spider.crawl_result
    assert spider.crawl_result["http://example.com"]["urls"] == [
        "http://example.com/test"
    ]


@patch.object(Spider, "crawl")
@patch.object(Spider, "save_results")
def test_start_with_save_to_file(
    mock_save_results: MagicMock, mock_crawl: MagicMock
) -> None:
    spider = Spider("http://example.com", 10, save_to_file="file.txt")
    mock_crawl.side_effect = lambda url: spider.crawl_result.update(
        {url: {"urls": ["http://example.com/test"]}}
    )

    spider.start()

    assert mock_crawl.call_count == 1
    assert "http://example.com" in spider.crawl_result
    assert spider.crawl_result["http://example.com"]["urls"] == [
        "http://example.com/test"
    ]

    mock_save_results.assert_called_once()
