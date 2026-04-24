"""
SET UP INSTRUCTIONS
-------------------

1. Follow the instructions here (https://docs.slack.dev/tools/bolt-python/building-an-app) to create a Slack app, 
install it in your workspace, and get a SLACK_BOT_TOKEN and SLACK_APP_TOKEN.

2. Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in your .env file

3. In your Slack app settings, under Features -> OAuth & Permissions grant the following Scopes: chat:write, 
im:history, reactions:write, users:read, files:read

4. In your Slack app settings, under Features -> Event Subscriptions -> Subscribe to bot events add a subscription
to message.im events

5. Under Features -> Slash Commands, create two new commands:
- /channels - no parameters, will return a list of channels and their assigned modules
- /channel [channel number] - will trigger a print of the specified channel (e.g. /channel 1)

Any messages sent to your bot (including images and links) will now be printed!
"""
from io import BytesIO
import os
import asyncio
import logging
import aiohttp

from app.config import TextConfig, settings
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from app.main import trigger_channel
from app.modules import text
from app.hardware import try_begin_print_job, clear_print_reservation

from PIL import Image

from app.utils import prepare_image_for_print

# Use a placeholder token to allow the module to be imported during tests 
# without requiring a live SLACK_BOT_TOKEN in the environment.
slackApp = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN", "xoxb-dummy-token"))
printerRef = None

logger = logging.getLogger(__name__)

def init(printer):
    global printerRef
    printerRef = printer
    handler = AsyncSocketModeHandler(slackApp, os.environ["SLACK_APP_TOKEN"])
    return handler.start_async()

@slackApp.event({"type": "message"})
async def print_message(body, client, ack):
    event = body.get("event", {})
    await ack_message(client, ack, event)

    # Get the user's display name
    user = await get_slack_user_name(client, event.get("user"))

    # Reserve the printer
    if not try_begin_print_job(debounce=False):
        logger.info("Skipping Slack message print: printer is busy.")
        return

    try:
        blocks = event.get('blocks', [])

        # Extract any hyperlinks for QR code printing
        urls = extract_urls(blocks)

        # Extract any images for printing
        images = await extract_images(event, client.token)

        # Convert Slack blocks to Tiptap format for printing
        content_doc = slack_to_tiptap(blocks, urls)

        def _do_slack_print():
            # Prepare printer for new job
            if hasattr(printerRef, "reset_buffer"):
                max_lines = getattr(settings, "max_print_lines", 200)
                printerRef.reset_buffer(max_lines)

            text.format_text_receipt(printerRef, TextConfig(content_doc=content_doc), "SLACK", f"From: {user}")

            # Print QR codes for any links found in the message
            for i, url in enumerate(urls, 1):
                printerRef.feed(2)

                # Ensure URL is absolute for QR code
                qr_url = url
                if not qr_url.startswith(("http://", "https://")):
                    qr_url = "https://" + qr_url
                
                # Print the index and URL as text above the QR code
                printerRef.print_body(f"[{i}]")

                # Print the QR code
                printerRef.print_qr(
                    data=qr_url,
                    error_correction="H" # Highest level of error correction to maximize scanability from print
                )
            
            # Print any images attached to the message
            for image in images:
                printerRef.feed(2)
                printerRef.print_image(image)

            # Flush to hardware
            if hasattr(printerRef, "flush_buffer"):
                printerRef.flush_buffer()

        # Use the default executor for CPU/IO-bound printing tasks to avoid blocking the loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _do_slack_print)
    finally:
        clear_print_reservation(clear_hold=False)

    await indicate_message_printed(client, event)

@slackApp.command("/channels")
async def get_channels(ack, respond):
    # Acknowledge command request
    await ack()

    channel_listing = "CHANNELS\n"
    for channel_num in range(1, 9):
        channel = settings.channels.get(channel_num)
        if channel and channel.modules:
            names = []
            for assignment in sorted(channel.modules, key=lambda m: m.order):
                module = settings.modules.get(assignment.module_id)
                if module:
                    names.append(module.name)
            if names:
                channel_listing += f"{channel_num}: {' + '.join(names)}\n"
            else:
                channel_listing += f"{channel_num}: (empty)\n"
        else:
            channel_listing += f"{channel_num}: (empty)\n"

    await respond(channel_listing)

@slackApp.command("/channel")
async def print_channel(ack, respond, command):
    # Acknowledge command request
    await ack()

    channel_num = command.get("text", "").strip()

    if not channel_num.isdigit() or int(channel_num) not in settings.channels:
        await respond(f"Invalid channel number: {channel_num}. Please provide a number between 1 and 8.")
        return

    channel_num = int(channel_num)
    channel = settings.channels.get(channel_num)
    
    if not channel or not channel.modules:
        await respond(f"Channel {channel_num} is empty")
        return
    
    if not try_begin_print_job(debounce=False):
        await respond(f"🖨️ Cannot print channel {channel_num} right now: printer is busy.")
        return
    
    await respond(f"🖨️ Triggering print for channel {channel_num}...")
    await trigger_channel(channel_num)
    await respond(f"✅ Triggered print for channel {channel_num}.")

async def ack_message(client, ack, message):
    # Acknowledge receipt of the message
    await ack()

    # React with eyes to indicate receipt of message
    await client.reactions_add(
        channel=message.get("channel"),
        timestamp=message.get("ts"),
        name="eyes",
    )

async def indicate_message_printed(client, message):
    # Remove eyes reaction and react with printer to indcate a successful print
    await client.reactions_remove(
        channel=message.get("channel"),
        timestamp=message.get("ts"),
        name="eyes",
    )
    await client.reactions_add(
        channel=message.get("channel"),
        timestamp=message.get("ts"),
        name="printer",
    )

async def get_slack_user_name(client, user_id):
    try:
        response = await client.users_info(user=user_id)
        if response and response.data:
            return response.data.get("user", {}).get("real_name", "UNKNOWN") 
        return "UNKNOWN"
    except Exception as e:
        logger.error(f"Failed to fetch Slack user info for {user_id}: {e}")
        return "UNKNOWN"

async def extract_images(event, token):
    """Downloads and processes any image attachments from a Slack message event."""
    images = []
    image_files = [f for f in event.get("files", []) if f.get("mimetype", "").startswith("image/")]
    
    if not image_files:
        return images

    async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {token}"}) as session:
        for file in image_files:
            try:
                async with session.get(file.get("url_private_download")) as resp:
                    if resp.status != 200:
                        raise Exception(f"Download failed with status {resp.status}")

                    image_data = await resp.read()
                    image = Image.open(BytesIO(image_data))
                    images.append(prepare_image_for_print(image))
            except Exception as e:
                logger.error(f"Unable to download and process image: {e}")
                continue
    return images

def extract_urls(slack_blocks):
    """Recursively extracts unique URLs from Slack blocks."""
    urls = []

    def _walk(elements):
        for el in elements:
            if el.get("type") == "link":
                url = el.get("url")
                if url and url not in urls:
                    urls.append(url)
            if "elements" in el:
                _walk(el["elements"])

    for block in slack_blocks:
        if "elements" in block:
            _walk(block["elements"])
    return urls

def slack_to_tiptap(slack_blocks, urls=None):
    """
    Converts Slack Block Kit blocks to Tiptap JSON format.
    Handles Headings, HRs, Lists (Bullet, Ordered, Task), Code, and Quotes.
    """
    tiptap_doc = {
        "type": "doc",
        "content": []
    }

    for block in slack_blocks:
        block_type = block.get("type")

        # 1. Headings (Slack 'header')
        if block_type == "header":
            text = block.get("text", {}).get("text", "")
            tiptap_doc["content"].append({
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": text}]
            })

        # 2. Horizontal Rule (Slack 'divider')
        elif block_type == "divider":
            tiptap_doc["content"].append({"type": "horizontalRule"})

        # 3. Rich Text Container
        elif block_type == "rich_text":
            for element in block.get("elements", []):
                tiptap_node = process_rich_text_element(element, urls)
                if tiptap_node:
                    # If process_rich_text_element returns a list (for quotes), extend the content
                    if isinstance(tiptap_node, list):
                        tiptap_doc["content"].extend(tiptap_node)
                    else:
                        tiptap_doc["content"].append(tiptap_node)

    return tiptap_doc

def process_rich_text_element(element, urls=None):
    """Maps Slack rich_text elements to Tiptap nodes."""
    el_type = element.get("type")

    # Paragraphs (rich_text_section)
    if el_type == "rich_text_section":
        return {
            "type": "paragraph",
            "content": [transform_text(item, urls) for item in element.get("elements", []) if item.get("type") in ["text", "link"]]
        }

    # Code Blocks (rich_text_preformatted) -> Extracted to Paragraph
    elif el_type == "rich_text_preformatted":
        return {
            "type": "paragraph",
            "content": [transform_text(item, urls) for item in element.get("elements", []) if item.get("type") in ["text", "link"]]
        }

    # Quote Blocks (rich_text_quote) -> Extracted to Paragraph(s)
    elif el_type == "rich_text_quote":
        # A quote can contain multiple sections. We'll return a list of paragraphs.
        paragraphs = []
        for inner in element.get("elements", []):
            if inner.get("type") == "rich_text_section":
                paragraphs.append({
                    "type": "paragraph",
                    "content": [transform_text(item, urls) for item in inner.get("elements", []) if item.get("type") in ["text", "link"]]
                })
        return paragraphs

    # Lists (rich_text_list)
    elif el_type == "rich_text_list":
        style = element.get("style")
        list_map = {"bullet": "bulletList", "ordered": "orderedList"}
        
        node_type = list_map.get(style, "bulletList")
        item_type = "listItem"

        if style == "checked":
            node_type = "taskList"
            item_type = "taskItem"

        list_content = []
        for item in element.get("elements", []):
            inner_content = [transform_text(t, urls) for t in item.get("elements", []) if t.get("type") in ["text", "link"]]
            list_item = {
                "type": item_type,
                "content": [{"type": "paragraph", "content": inner_content}]
            }
            if item_type == "taskItem":
                list_item["attrs"] = {"checked": True}
            list_content.append(list_item)

        return {"type": node_type, "content": list_content}

    return None

def transform_text(slack_text_obj, urls=None):
    """Converts Slack text objects and their styles to Tiptap marks."""
    url = slack_text_obj.get("url")
    if url and urls and url in urls:
        # Replace the link text with the reference number [N]
        idx = urls.index(url) + 1

        # If the hyperlink had text, include it before the reference number for better readability on print
        if slack_text_obj.get("text"): 
            text = f"{slack_text_obj.get('text')}[{idx}]"
        else:
            text = f"[{idx}]"
    else:
        text = slack_text_obj.get("text") or url or ""
        
    styles = slack_text_obj.get("style", {})
    
    marks = []
    if styles.get("bold"): marks.append({"type": "bold"})
    if styles.get("italic"): marks.append({"type": "italic"})

    node = {"type": "text", "text": text}
    if marks: node["marks"] = marks
    return node