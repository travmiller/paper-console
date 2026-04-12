import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from io import BytesIO
from PIL import Image

from app.slack_client import (
    extract_urls,
    transform_text,
    slack_to_tiptap,
    extract_images,
    get_slack_user_name,
    print_message
)

# --- Helper Mocks ---

@pytest.fixture
def mock_printer():
    printer = MagicMock()
    printer.reset_buffer = MagicMock()
    printer.print_header = MagicMock()
    printer.print_body = MagicMock()
    printer.print_qr = MagicMock()
    printer.print_image = MagicMock()
    printer.flush_buffer = MagicMock()
    printer.feed = MagicMock()
    return printer

@pytest.fixture
def mock_slack_client():
    client = AsyncMock()
    client.token = "xoxb-fake-token"
    return client

# --- Unit Tests for Utility Functions ---

def test_extract_urls():
    """Test that URLs are extracted from nested block structures."""
    blocks = [
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [
                        {"type": "text", "text": "Visit "},
                        {"type": "link", "url": "https://google.com"},
                        {"type": "text", "text": " and "},
                        {"type": "link", "url": "https://github.com"},
                        {"type": "text", "text": " and "},
                        {"type": "link", "url": "https://github.com"}
                    ]
                }
            ]
        },
        {"type": "divider"} # Edge case: block without elements
    ]
    urls = extract_urls(blocks)
    assert urls == ["https://google.com", "https://github.com"]
    assert extract_urls([]) == []

def test_transform_text_styles():
    """Test Tiptap mark conversion for bold and italic styles."""
    slack_text = {
        "type": "text",
        "text": "Hello World",
        "style": {"bold": True, "italic": True}
    }
    result = transform_text(slack_text)
    assert result["text"] == "Hello World"
    assert {"type": "bold"} in result["marks"]
    assert {"type": "italic"} in result["marks"]

def test_transform_text_with_links():
    """Test that links are transformed into indexed references [N]."""
    urls = ["https://google.com", "https://slack.com"]
    slack_link = {
        "type": "link",
        "url": "https://slack.com",
        "text": "Slack"
    }
    # Case: Link with text
    result = transform_text(slack_link, urls)
    assert result["text"] == "Slack[2]"

    # Case: Link without text
    slack_link_no_text = {"type": "link", "url": "https://google.com"}
    result_no_text = transform_text(slack_link_no_text, urls)
    assert result_no_text["text"] == "[1]"

def test_slack_to_tiptap_conversion():
    """Test the overall conversion from Slack blocks to Tiptap JSON."""
    blocks = [
        {"type": "header", "text": {"text": "My Heading"}},
        {"type": "divider"},
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Paragraph content"}]
                }
            ]
        }
    ]
    doc = slack_to_tiptap(blocks)
    assert doc["type"] == "doc"
    assert doc["content"][0]["type"] == "heading"
    assert doc["content"][1]["type"] == "horizontalRule"
    assert doc["content"][2]["type"] == "paragraph"

# --- Async Tests ---

@pytest.mark.asyncio
async def test_get_slack_user_name_success(mock_slack_client):
    """Test successful user name fetching."""
    mock_slack_client.users_info.return_value.data = {
        "user": {"real_name": "Bob"}
    }
    name = await get_slack_user_name(mock_slack_client, "U123")
    assert name == "Bob"

@pytest.mark.asyncio
async def test_get_slack_user_name_failure(mock_slack_client):
    """Test fallback when user info cannot be fetched."""
    mock_slack_client.users_info.side_effect = Exception("API Error")
    name = await get_slack_user_name(mock_slack_client, "U123")
    assert name == "UNKNOWN"

@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_extract_images_edge_cases(mock_get, mock_slack_client):
    """Test image extraction with various network outcomes."""
    event = {
        "files": [
            {"mimetype": "image/jpeg", "url_private_download": "http://fake.com/img.jpg"},
            {"mimetype": "application/pdf", "url_private_download": "http://fake.com/doc.pdf"}
        ]
    }
    
    # Create a dummy image
    img = Image.new('RGB', (100, 100))
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    
    # Mock aiohttp response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read = AsyncMock(return_value=img_byte_arr.getvalue())
    mock_response.__aenter__.return_value = mock_response
    mock_get.return_value = mock_response

    images = await extract_images(event, "token")
    assert len(images) == 1  # Should ignore the PDF
    assert isinstance(images[0], Image.Image)
    
    # Test download failure (e.g. 404)
    mock_response.status = 404
    images_fail = await extract_images(event, "token")
    assert len(images_fail) == 0

# --- Integration/Flow Test ---

@pytest.mark.asyncio
@patch("app.slack_client.try_begin_print_job")
@patch("app.slack_client.clear_print_reservation")
@patch("app.slack_client.extract_images")
@patch("app.slack_client.get_slack_user_name")
async def test_print_message_flow(
    mock_get_name, 
    mock_ext_img, 
    mock_clear, 
    mock_try_job, 
    mock_slack_client, 
    mock_printer
):
    """Tests the full message handling flow including all message types combined."""
    from app import slack_client
    slack_client.printerRef = mock_printer
    
    mock_try_job.return_value = True
    mock_get_name.return_value = "TestUser"
    
    # Mock 1 image returned
    dummy_img = Image.new('1', (384, 100))
    mock_ext_img.return_value = [dummy_img]
    
    # Complex event: Text + Link + Blocks
    event_body = {
        "event": {
            "user": "U123",
            "channel": "C123",
            "ts": "1234.5678",
            "blocks": [
                {
                    "type": "rich_text",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [
                                {"type": "text", "text": "Check this link: "},
                                {"type": "link", "url": "https://example.com"}
                            ]
                        }
                    ]
                }
            ],
            "files": [{"mimetype": "image/png"}]
        }
    }
    
    mock_ack = AsyncMock()
    
    # Run the main entry point
    await print_message(event_body, mock_slack_client, mock_ack)
    
    # Verifications
    mock_ack.assert_called_once()
    
    # Verify hardware interactions via the thread pool executor
    # Note: Since the real code uses a background thread pool, 
    # we allow a brief moment for execution or verify mocks if run synchronously.
    # In this test environment, we rely on the mocked logic.
    
    # Check that reactions were added
    assert mock_slack_client.reactions_add.call_count == 2 # 'eyes' then 'printer'
    
    # Ensure printer was reserved and released
    mock_try_job.assert_called_once()
    mock_clear.assert_called_once()