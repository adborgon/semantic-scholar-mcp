"""Test cases for SemanticScholarServer."""

from unittest.mock import MagicMock, patch

import pytest
from mcp.types import TextContent

from semantic_scholar_mcp.server import SemanticScholarServer, add_abstract


class TestSemanticScholarServer:
    """Test cases for SemanticScholarServer class."""

    def test_init_without_api_key(self, server_without_api_key: SemanticScholarServer):
        """Test server initialization without API key."""
        assert server_without_api_key.api_key is None
        assert (
            server_without_api_key.base_url
            == "https://api.semanticscholar.org/graph/v1"
        )
        assert server_without_api_key.server.name == "semantic-scholar-mcp"

    def test_init_with_api_key(
        self, server_with_api_key: SemanticScholarServer, mock_api_key: str
    ):
        """Test server initialization with API key."""
        assert server_with_api_key.api_key == mock_api_key
        assert (
            server_with_api_key.base_url == "https://api.semanticscholar.org/graph/v1"
        )

    def test_get_headers_without_api_key(
        self, server_without_api_key: SemanticScholarServer
    ):
        """Test headers generation without API key."""
        headers = server_without_api_key._get_headers()
        expected = {"Accept": "application/json"}
        assert headers == expected

    def test_get_headers_with_api_key(
        self, server_with_api_key: SemanticScholarServer, mock_api_key: str
    ):
        """Test headers generation with API key."""
        headers = server_with_api_key._get_headers()
        expected = {"Accept": "application/json", "x-api-key": mock_api_key}
        assert headers == expected

    def test_server_setup_methods_exist(
        self, server_without_api_key: SemanticScholarServer
    ):
        """Test that server setup methods exist."""
        # Check that setup methods exist
        assert hasattr(server_without_api_key, "_setup_tools")
        assert hasattr(server_without_api_key, "_setup_resources")
        assert hasattr(server_without_api_key, "_setup_handlers")

        # Check that the server object exists and has expected properties
        assert hasattr(server_without_api_key, "server")
        assert server_without_api_key.server.name == "semantic-scholar-mcp"

    def test_default_fields(self, server_without_api_key: SemanticScholarServer):
        """Test default field configurations."""
        assert (
            server_without_api_key.search_paper_default_fields
            == "paperId,title,abstract,authors,year,citationCount"
        )
        assert (
            server_without_api_key.get_paper_default_fields
            == "paperId,title,abstract,authors,year,citationCount,referenceCount,fieldsOfStudy,publicationTypes,publicationDate,journal,openAccessPdf"
        )
        assert (
            server_without_api_key.get_authors_default_fields
            == "authorId,name,affiliations,citationCount,hIndex"
        )


class TestToolHandlers:
    """Test cases for tool handlers."""

    @pytest.mark.anyio
    async def test_handle_search_paper_success(
        self,
        server_without_api_key: SemanticScholarServer,
        sample_search_response: dict,
    ):
        """Test successful paper search."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_search_response
            mock_to_thread.return_value = mock_response

            # Test the search
            args = {"query": "machine learning"}
            result = await server_without_api_key._handle_search_paper(args)

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert "Sample Paper Title" in str(result[0].text)

    @pytest.mark.anyio
    async def test_handle_search_paper_api_error(
        self, server_without_api_key: SemanticScholarServer
    ):
        """Test paper search with API error."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock error response
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_to_thread.return_value = mock_response

            args = {"query": "machine learning"}
            result = await server_without_api_key._handle_search_paper(args)

            assert len(result) == 1
            assert "Error: API returned status 500" in result[0].text

    @pytest.mark.anyio
    async def test_handle_search_paper_exception(
        self, server_without_api_key: SemanticScholarServer
    ):
        """Test paper search with exception."""
        with patch("asyncio.to_thread", side_effect=Exception("Network error")):
            args = {"query": "machine learning"}
            result = await server_without_api_key._handle_search_paper(args)

            assert len(result) == 1
            assert "Error searching papers: Network error" in result[0].text

    @pytest.mark.anyio
    async def test_handle_get_paper_success(
        self, server_without_api_key: SemanticScholarServer, sample_paper_response: dict
    ):
        """Test successful paper retrieval."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_paper_response
            mock_to_thread.return_value = mock_response

            args = {"paper_id": "649def34f8be52c8b66281af98ae884c09aef38b"}
            result = await server_without_api_key._handle_get_paper(args)

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert "Sample Paper Title" in str(result[0].text)

    @pytest.mark.anyio
    async def test_handle_get_paper_not_found(
        self, server_without_api_key: SemanticScholarServer
    ):
        """Test paper retrieval with 404 error."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock 404 response
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_to_thread.return_value = mock_response

            args = {"paper_id": "nonexistent"}
            result = await server_without_api_key._handle_get_paper(args)

            assert len(result) == 1
            assert "Paper not found: nonexistent" in result[0].text

    @pytest.mark.anyio
    async def test_handle_get_authors_success(
        self,
        server_without_api_key: SemanticScholarServer,
        sample_authors_response: dict,
    ):
        """Test successful authors retrieval."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_authors_response
            mock_to_thread.return_value = mock_response

            args = {"paper_id": "649def34f8be52c8b66281af98ae884c09aef38b"}
            result = await server_without_api_key._handle_get_authors(args)

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            # The response dict must be serialized to text, not returned raw
            # (a raw dict raises a Pydantic ValidationError inside the try
            # block, which is swallowed and returned as an error message).
            assert "John Doe" in str(result[0].text)
            assert "Error getting authors" not in str(result[0].text)

    @pytest.mark.anyio
    async def test_handle_get_citation_success(
        self,
        server_without_api_key: SemanticScholarServer,
        sample_citation_response: dict,
    ):
        """Test successful citation retrieval."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_citation_response
            mock_to_thread.return_value = mock_response

            args = {
                "paper_id": "649def34f8be52c8b66281af98ae884c09aef38b",
                "format": "bibtex",
            }
            result = await server_without_api_key._handle_get_citation(args)

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert "@article" in str(result[0].text)
            assert "Error generating citation" not in str(result[0].text)

    @pytest.mark.anyio
    async def test_handle_get_citation_format_not_available(
        self, server_without_api_key: SemanticScholarServer
    ):
        """Test citation retrieval with unavailable format."""
        citation_response = {
            "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
            "citationStyles": {"bibtex": "@article{...}"},
            "abstract": "Sample abstract",
        }

        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = citation_response
            mock_to_thread.return_value = mock_response

            args = {
                "paper_id": "649def34f8be52c8b66281af98ae884c09aef38b",
                "format": "apa",
            }
            result = await server_without_api_key._handle_get_citation(args)

            assert len(result) == 1
            assert "Citation format 'apa' not available" in result[0].text

    @pytest.mark.anyio
    async def test_handle_get_citation_separate_abstract_request(
        self, server_without_api_key: SemanticScholarServer
    ):
        """Test that citation and abstract are fetched in separate requests.

        The Semantic Scholar API rejects `abstract` when requested together
        with `citationStyles`, so the handler must issue two requests and
        normalize style keys (e.g. 'APA' -> 'apa').
        """
        citation_response = {
            "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
            "citationStyles": {
                "APA": "Doe, J. (2023). Sample Paper Title."
            },  # API may return capitalized keys
        }
        abstract_response = {
            "abstract": "This is a standalone abstract fetched separately."
        }

        with patch("asyncio.to_thread") as mock_to_thread:
            citation_mock = MagicMock()
            citation_mock.status_code = 200
            citation_mock.json.return_value = citation_response

            abstract_mock = MagicMock()
            abstract_mock.status_code = 200
            abstract_mock.json.return_value = abstract_response

            mock_to_thread.side_effect = [citation_mock, abstract_mock]

            args = {
                "paper_id": "649def34f8be52c8b66281af98ae884c09aef38b",
                "format": "apa",
            }
            result = await server_without_api_key._handle_get_citation(args)

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert mock_to_thread.call_count == 2
            # The abstract is appended to the citation text
            assert result[0].text == (
                "Doe, J. (2023). Sample Paper Title.\n\n"
                "Abstract: This is a standalone abstract fetched separately."
            )

    def test_server_configuration(self, server_without_api_key: SemanticScholarServer):
        """Test basic server configuration."""
        # Test that server is properly configured
        assert server_without_api_key.server.name == "semantic-scholar-mcp"
        assert (
            server_without_api_key.base_url
            == "https://api.semanticscholar.org/graph/v1"
        )

        # Test that default field configurations exist
        assert hasattr(server_without_api_key, "search_paper_default_fields")
        assert hasattr(server_without_api_key, "get_paper_default_fields")
        assert hasattr(server_without_api_key, "get_authors_default_fields")


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_add_abstract_bibtex(self):
        """Test that add_abstract inserts the abstract field into BibTeX."""
        citation = "@article{doe2023sample,\n  title = {Sample}\n}"
        abstract = "This is a sample abstract."
        result = add_abstract(citation, abstract, "bibtex")

        assert "abstract = {This is a sample abstract.}" in result
        assert result.strip().endswith("}")
        assert result.index("abstract = {") < result.rfind("}")

    def test_add_abstract_apa(self):
        """Test that add_abstract appends the abstract to APA citations."""
        citation = "Doe, J. (2023). Sample Paper Title."
        abstract = "This is a sample abstract."
        result = add_abstract(citation, abstract, "apa")

        assert result == "Doe, J. (2023). Sample Paper Title.\n\nAbstract: This is a sample abstract."

    def test_add_abstract_empty(self):
        """Test that add_abstract returns the citation unchanged if empty."""
        citation = "@article{doe2023sample, title = {Sample}}"
        assert add_abstract(citation, "", "bibtex") == citation
        assert add_abstract(citation, "", "apa") == citation
