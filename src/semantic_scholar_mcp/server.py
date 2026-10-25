"""Semantic Scholar MCP Server implementation."""

import asyncio
from typing import Any

import requests
from mcp.server import Server
from mcp.types import Resource, TextContent, Tool


# Shown in every tool description so that agents that read tool schemas
# schedule their calls respecting the strict API rate limit.
RATE_LIMIT_WARNING = (
    "IMPORTANT: the Semantic Scholar API enforces a strict rate limit of "
    "about 1 request per second even with an API key. Wait at least 1 "
    "second between consecutive tool calls; on HTTP 429 wait 15-20 seconds "
    "and retry."
)


class SemanticScholarServer:
    """MCP server for Semantic Scholar operations."""

    def __init__(self, api_key: str | None = None) -> None:
        self.server = Server("semantic-scholar-mcp")
        self.api_key = api_key
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self._setup_tools()
        self._setup_resources()
        self._setup_handlers()

    def _setup_tools(self) -> None:
        """Register available tools."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="search_paper",
                    description="Search for papers using Semantic Scholar. Use 'fields' parameter to customize returned data. "
                    + RATE_LIMIT_WARNING,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": """A plain-text search query string.\n\n- No special query syntax is supported\n- Hyphenated query terms yield no matches (replace it with space to find matches).""",
                            },
                            "fields": {
                                "type": "string",
                                "description": """A comma-separated list of the fields to be returned. The paperId field is always returned. See the resource 'semantic-scholar://fields/paper' for available fields.\n\nExamples:\n- `title,url`\n- `title,embedding.specter_v2`\n- `title,authors,citations.title,citations.abstract`
                                """,
                                "default": self.search_paper_default_fields,
                            },
                            "publicationTypes": {
                                "type": "string",
                                "description": """A comma-separated list of publication types to include.\n\nAvailable types: Review, JournalArticle, CaseReort, ClinicalTrial, Conference, Dataset, Editorial, LettersAndComments, MetaAnalysis, News, Study, Book, BookSection\nExample: `Review,JournalArticle` will return papers with publication types Review and/or JournalArticle""",
                            },
                            "openAccessPdf": {
                                "type": "boolean",
                                "description": "Restricts results to only include papers with a public PDF.",
                                "default": False,
                            },
                            "minCitationCount": {
                                "type": "integer",
                                "description": "Restricts results to only include papers with the minimum number of citations.",
                                "default": 0,
                            },
                            "publicationDateOrYear": {
                                "type": "string",
                                "description": """Restricts results to the given range of publication dates or years (inclusive). Accepts the format `<startDate>:<endDate>` with each date in `YYYY-MM-DD` format.\nEach term is optional, allowing for specific dates, fixed ranges, or open-ended ranges. In addition, prefixes are suported as a shorthand, e.g. `2020-06` matches all dates in June 2020.\nSpecific dates are not known for all papers, so some records returned with this filter will have a `null` value for publicationDate. `year`, however, will always be present. For records where a specific publication date is not known, they will be treated as if published on January 1st of their publication year.\n\nExamples:\n\n- `2019-03-05` on March 3rd, 2019\n- `2019-03` during March 2019\n- `2019` during 2019\n- `2016-03-05:2020-06-06` as early as March 5th, 2016 or as late as June 6th, 2020\n- `1981-08-25:` on or after August 25th, 1981\n- `:2015-01` before or on January 31st, 2015\n- `2015:2020` between January 1st, 2015 and December 31st, 2020
""",
                            },
                            "year": {
                                "type": "string",
                                "description": """Restricts results to the given publication year or range of years (inclusive).\n\nExamples:\n\n- `2019` in 2019\n- `2016-2020` as early as 2016 or as late as 2020\n- `2010-` during or after 2010\n- `-2015` before or during 2015""",
                            },
                            "venue": {
                                "type": "string",
                                "description": """Restricts results to papers published in the given venues, formatted as a comma-separated list.\n\nInput could also be an ISO4 abbreviation. Examples include:\n- Nature\n- New England Journal of Medicine\n- Radiology\n- N. Engl. J. Med.\n\nExample: `Nature,Radiology` will return papers from venues Nature and/or Radiology.""",
                            },
                            "fieldsOfStudy": {
                                "type": "string",
                                "description": """A Comma-separated list of fields of study to include.\n\nAvailable fields of study: Computer Science,Medicine,Chemistry,Biology,Materials Science,Physics,Geology,Psychology,Art,History,Geography,Sociology,Business,Political Science,Economics,Philosophy,Mathematics,Engineering,Environmental Science,Agricultural and Food Sciences,Education,Law,Linguistics\nExample: `Physics,Mathematics` will return papers with either Physics or Mathematics in their list of fields-of-study.""",
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Starting position in the list of results",
                                "default": 0,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (max: 100)",
                                "default": 10,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="get_paper",
                    description="Get detailed information about a specific paper. Use 'fields' parameter to customize returned data. "
                    + RATE_LIMIT_WARNING,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "paper_id": {
                                "type": "string",
                                "description": """The following types of IDs are supported:\n- `<sha>` - a Semantic Scholar ID, e.g. `649def34f8be52c8b66281af98ae884c09aef38b`\n- `CorpusId:<id>` - a Semantic Scholar numerical ID, e.g. `CorpusId:215416146`\n- `DOI:<doi>` - a Digital Object Identifier, e.g. `DOI:10.18653/v1/N18-3011`\n- `ARXIV:<id>` - arXiv.rg, e.g. `ARXIV:2106.15928`\n- `MAG:<id>` - Microsoft Academic Graph, e.g. `MAG:112218234`\n- `ACL:<id>` - Association for Computational Linguistics, e.g. `ACL:W12-3903`\n- `PMID:<id>` - PubMed/Medline, e.g. `PMID:19872477`\n- `PMCID:<id>` - PubMed Central, e.g. `PMCID:2323736`\n- `URL:<url>` - URL from one of the sites listed below, e.g. `URL:https://arxiv.org/abs/2106.15928v1`\n\nURLs are recognized from the following sites:\n- semanticscholar.org\n- arxiv.org\n- aclweb.org\n- acm.org\n- biorxiv.org""",
                            },
                            "fields": {
                                "type": "string",
                                "description": """A comma-separated list of the fields to be returned. The paperId field is always returned. See the resource 'semantic-scholar://fields/paper' for available fields.\n\nExamples:\n- `title,url`\n- `title,embedding.specter_v2`\n- `title,authors,citations.title,citations.abstract`
                                """,
                                "default": self.get_paper_default_fields,
                            },
                        },
                        "required": ["paper_id"],
                    },
                ),
                Tool(
                    name="get_authors",
                    description="Get authors information for a specific paper. Use 'fields' parameter to customize author data returned. "
                    + RATE_LIMIT_WARNING,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "paper_id": {
                                "type": "string",
                                "description": """The following types of IDs are supported:\n- `<sha>` - a Semantic Scholar ID, e.g. `649def34f8be52c8b66281af98ae884c09aef38b`\n- `CorpusId:<id>` - a Semantic Scholar numerical ID, e.g. `CorpusId:215416146`\n- `DOI:<doi>` - a Digital Object Identifier, e.g. `DOI:10.18653/v1/N18-3011`\n- `ARXIV:<id>` - arXiv.rg, e.g. `ARXIV:2106.15928`\n- `MAG:<id>` - Microsoft Academic Graph, e.g. `MAG:112218234`\n- `ACL:<id>` - Association for Computational Linguistics, e.g. `ACL:W12-3903`\n- `PMID:<id>` - PubMed/Medline, e.g. `PMID:19872477`\n- `PMCID:<id>` - PubMed Central, e.g. `PMCID:2323736`\n- `URL:<url>` - URL from one of the sites listed below, e.g. `URL:https://arxiv.org/abs/2106.15928v1`\n\nURLs are recognized from the following sites:\n- semanticscholar.org\n- arxiv.org\n- aclweb.org\n- acm.org\n- biorxiv.org""",
                            },
                            "fields": {
                                "type": "string",
                                "description": """A comma-separated list of the fields to be returned. The authorId field is always returned. See the resource 'semantic-scholar://fields/author' for available fields.\n\nExamples:\n- `name,affiliations,papers`\n- `url,papers.year,papers.authors`
                                """,
                                "default": "authorId,name,affiliations,citationCount,hIndex",
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Used for pagination. When returning a list of results, start with the element at this position in the list.",
                                "default": 0,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "The maximum number of results to return. Maximum is 1000.",
                                "default": 100,
                            },
                        },
                        "required": ["paper_id"],
                    },
                ),
                Tool(
                    name="get_citation",
                    description="Get citation information in various formats. " + RATE_LIMIT_WARNING,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "paper_id": {
                                "type": "string",
                                "description": """The following types of IDs are supported:\n- `<sha>` - a Semantic Scholar ID, e.g. `649def34f8be52c8b66281af98ae884c09aef38b`\n- `CorpusId:<id>` - a Semantic Scholar numerical ID, e.g. `CorpusId:215416146`\n- `DOI:<doi>` - a Digital Object Identifier, e.g. `DOI:10.18653/v1/N18-3011`\n- `ARXIV:<id>` - arXiv.rg, e.g. `ARXIV:2106.15928`\n- `MAG:<id>` - Microsoft Academic Graph, e.g. `MAG:112218234`\n- `ACL:<id>` - Association for Computational Linguistics, e.g. `ACL:W12-3903`\n- `PMID:<id>` - PubMed/Medline, e.g. `PMID:19872477`\n- `PMCID:<id>` - PubMed Central, e.g. `PMCID:2323736`\n- `URL:<url>` - URL from one of the sites listed below, e.g. `URL:https://arxiv.org/abs/2106.15928v1`\n\nURLs are recognized from the following sites:\n- semanticscholar.org\n- arxiv.org\n- aclweb.org\n- acm.org\n- biorxiv.org""",
                            },
                            "format": {
                                "type": "string",
                                "description": "Citation format: 'bibtex', 'apa', 'mla', or 'chicago'",
                                "default": "bibtex",
                            },
                        },
                        "required": ["paper_id"],
                    },
                ),
            ]

    def _setup_resources(self) -> None:
        """Register available resources."""

        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="semantic-scholar://fields/paper",  # type: ignore
                    name="Paper Fields Reference",
                    description="Complete list of available fields for paper-related tools",
                    mimeType="text/markdown",
                ),
                Resource(
                    uri="semantic-scholar://fields/author",  # type: ignore
                    name="Author Fields Reference",
                    description="Complete list of available fields for author-related tools",
                    mimeType="text/markdown",
                ),
            ]

        @self.server.read_resource()  # type: ignore
        async def handle_read_resource(uri: str) -> str:
            """Read resource content."""
            if uri == "semantic-scholar://fields/paper":
                return self._get_paper_fields_documentation()
            elif uri == "semantic-scholar://fields/author":
                return self._get_author_fields_documentation()
            else:
                raise ValueError(f"Unknown resource: {uri}")

    def _get_paper_fields_documentation(self) -> str:
        """Get paper fields documentation."""
        return """# Paper Fields Reference\n\n## Basic Fields\n- `paperId` - Unique paper identifier\n- `title` - Paper title\n- `abstract` - Paper abstract\n- `year` - Publication year\n- `publicationDate` - Full publication date (YYYY-MM-DD)\n\n## Author Information\n- `authors` - List of authors (returns authorId and name by default)\n- `authors.authorId` - Author's unique identifier\n- `authors.name` - Author's name\n- `authors.affiliations` - Author's institutional affiliations\n- `authors.citationCount` - Author's total citation count\n- `authors.hIndex` - Author's h-index\n\n## Citation and Reference Data\n- `citationCount` - Number of times this paper has been cited\n- `referenceCount` - Number of references in this paper\n- `citations` - List of papers that cite this paper\n- `references` - List of papers referenced by this paper\n\n## Publication Details\n- `journal` - Journal information (name, volume, pages, etc.)\n- `venue` - Publication venue\n- `publicationTypes` - Types of publication (e.g., JournalArticle, Conference)\n- `fieldsOfStudy` - Academic fields (e.g., Computer Science, Medicine)\n- `s2FieldsOfStudy` - Semantic Scholar's field classifications\n\n## Additional Metadata\n- `doi` - Digital Object Identifier\n- `arxivId` - ArXiv identifier\n- `url` - Paper URL\n- `openAccessPdf` - Open access PDF information\n- `embedding` - Paper embedding vectors (for similarity analysis)\n"""

    def _get_author_fields_documentation(self) -> str:
        """Get author fields documentation."""
        return """# Author Fields Reference\n\n## Available Fields\n- `authorId` - Unique author identifier\n- `name` - Author's name\n- `affiliations` - Institutional affiliations (array)\n- `citationCount` - Total citation count across all papers\n- `hIndex` - h-index metric\n- `paperCount` - Number of papers published\n- `url` - Author's Semantic Scholar profile URL\n"""

    def _setup_handlers(self) -> None:
        """Setup tool call handlers."""

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[TextContent]:
            """Handle tool calls."""
            if name == "search_paper":
                return await self._handle_search_paper(arguments)
            elif name == "get_paper":
                return await self._handle_get_paper(arguments)
            elif name == "get_authors":
                return await self._handle_get_authors(arguments)
            elif name == "get_citation":
                return await self._handle_get_citation(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    search_paper_default_fields = "paperId,title,abstract,authors,year,citationCount"

    async def _handle_search_paper(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Handle paper search requests."""
        try:
            params = {
                "query": arguments["query"],
                "fields": arguments.get("fields", self.search_paper_default_fields),
                "offset": arguments.get("offset", 0),
                "limit": min(arguments.get("limit", 10), 100),
            }

            for queryParams in [
                "publicationTypes",
                "minCitationCount",
                "publicationDateOrYear",
                "year",
                "venue",
                "fieldsOfStudy",
            ]:
                if queryParams in arguments:
                    params[queryParams] = arguments[queryParams]
            if arguments.get("openAccessPdf"):
                params["openAccessPdf"] = ""

            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/search",
                params=params,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: API returned status {response.status_code}: {response.text}",
                    )
                ]

            res = response.json()

            return [TextContent(type="text", text=str(res))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching papers: {str(e)}")]

    get_paper_default_fields = "paperId,title,abstract,authors,year,citationCount,referenceCount,fieldsOfStudy,publicationTypes,publicationDate,journal,openAccessPdf"

    async def _handle_get_paper(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle get paper details requests."""
        try:
            paper_id = arguments["paper_id"]

            params = {"fields": arguments.get("fields", self.get_paper_default_fields)}

            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/{paper_id}",
                params=params,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 404:
                return [TextContent(type="text", text=f"Paper not found: {paper_id}")]
            elif response.status_code != 200:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: API returned status {response.status_code}: {response.text}",
                    )
                ]

            res = response.json()

            return [TextContent(type="text", text=str(res))]
        except Exception as e:
            return [
                TextContent(type="text", text=f"Error getting paper details: {str(e)}")
            ]

    get_authors_default_fields = "authorId,name,affiliations,citationCount,hIndex"

    async def _handle_get_authors(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle get paper authors requests."""
        try:
            paper_id = arguments["paper_id"]

            params = {
                "fields": arguments.get("fields", self.get_authors_default_fields),
                "offset": arguments.get("offset", 0),
                "limit": min(arguments.get("limit", 100), 1000),
            }

            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/{paper_id}/authors",
                params=params,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 404:
                return [TextContent(type="text", text=f"Paper not found: {paper_id}")]
            elif response.status_code != 200:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: API returned status {response.status_code}: {response.text}",
                    )
                ]

            res = response.json()

            return [TextContent(type="text", text=str(res))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting authors: {str(e)}")]

    async def _handle_get_citation(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Handle get citation requests."""
        try:
            paper_id = arguments["paper_id"]
            citation_format = arguments.get("format", "bibtex").lower()

            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/{paper_id}",
                params={"fields": "citationStyles"},
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 404:
                return [TextContent(type="text", text=f"Paper not found: {paper_id}")]
            elif response.status_code != 200:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: API returned status {response.status_code}: {response.text}",
                    )
                ]

            data = response.json()

            citation_styles = data.get("citationStyles") or {}
            available_formats = {
                str(key).lower(): value for key, value in citation_styles.items()
            }

            if not available_formats:
                return [
                    TextContent(
                        type="text", text="No citation styles available for this paper."
                    )
                ]
            if citation_format not in available_formats:
                return [
                    TextContent(
                        type="text",
                        text=f"Citation format '{citation_format}' not available. Available formats for this paper: {', '.join(sorted(available_formats))}",
                    )
                ]

            citation = available_formats[citation_format]
            abstract = await self._fetch_abstract(paper_id)

            result_text = add_abstract(citation, abstract, citation_format)
            return [TextContent(type="text", text=result_text)]
        except Exception as e:
            return [
                TextContent(type="text", text=f"Error generating citation: {str(e)}")
            ]

    async def _fetch_abstract(self, paper_id: str) -> str:
        """Fetch the paper abstract in a separate request.

        The Semantic Scholar API rejects `abstract` when it is requested
        together with `citationStyles`, so the abstract must be fetched in
        its own request. Returns an empty string if the request fails so
        that the citation is still returned without the abstract.
        """
        try:
            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/{paper_id}",
                params={"fields": "abstract"},
                headers=self._get_headers(),
                timeout=30,
            )
            if response.status_code != 200:
                return ""
            return response.json().get("abstract") or ""
        except Exception:
            return ""


def add_abstract(citation: str, abstract: str, citation_format: str) -> str:
    """Attach the paper abstract to a formatted citation.

    - BibTeX: inserts an ``abstract = {...}`` field inside the entry.
    - APA/MLA/Chicago: appends the abstract after the citation text.
    """
    if not abstract:
        return citation

    if citation_format == "bibtex":
        stripped = citation.rstrip()
        closing_index = stripped.rfind("}")
        if closing_index == -1:
            return stripped
        body = stripped[:closing_index].rstrip()
        if not body.endswith(","):
            body += ","
        return f"{body}\n  abstract = {{{abstract}}}\n{stripped[closing_index:]}"

    return f"{citation.rstrip()}\n\nAbstract: {abstract}"
