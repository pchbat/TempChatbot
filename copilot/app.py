# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# enable logging for Microsoft Agents library
# for more information, see README.md for Quickstart Agent
import logging
ms_agents_logger = logging.getLogger("microsoft.agents")
ms_agents_logger.addHandler(logging.StreamHandler())
ms_agents_logger.setLevel(logging.INFO)

import sys
from os import environ
import asyncio
import webbrowser

from dotenv import load_dotenv

from msal import PublicClientApplication

from microsoft.agents.activity import ActivityTypes, load_configuration_from_env
from microsoft.agents.copilotstudio.client import (
    ConnectionSettings,
    CopilotClient,
)

from local_token_cache import LocalTokenCache

# Load environment variables from .env file
load_dotenv()

# Set up logging for this specific script
# This allows us to see detailed debug messages from our own code
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG) # Set to DEBUG to see all log messages

TOKEN_CACHE = LocalTokenCache("./.local_token_cache.json")


async def open_browser(url: str):
    logger.debug(f"Opening browser at {url}")
    await asyncio.get_event_loop().run_in_executor(None, lambda: webbrowser.open(url))


def acquire_token(settings: ConnectionSettings, app_client_id, tenant_id):
    logger.info("Attempting to acquire authentication token.")
    pca = PublicClientApplication(
        client_id=app_client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=TOKEN_CACHE,
    )

    token_request = {
        "scopes": ["https://api.powerplatform.com/.default"],
    }
    accounts = pca.get_accounts()
    retry_interactive = False
    token = None

    logger.debug(f"Found {len(accounts)} cached accounts.")

    try:
        if accounts:
            logger.info("Attempting to acquire token silently using a cached account.")
            response = pca.acquire_token_silent(
                token_request["scopes"], account=accounts[0]
            )
            token = response.get("access_token")
            if token:
                logger.info("Successfully acquired token silently.")
            else:
                logger.warning("Silent token acquisition failed. No token in response.")
                retry_interactive = True
        else:
            logger.info("No cached accounts found. Proceeding to interactive login.")
            retry_interactive = True
    except Exception as e:
        retry_interactive = True
        logger.error(
            f"Error acquiring token silently: {e}. Going to attempt interactive login."
        )

    if retry_interactive:
        logger.info("Attempting interactive login...")
        try:
            response = pca.acquire_token_interactive(**token_request)
            token = response.get("access_token")
            if token:
                logger.info("Successfully acquired token interactively.")
            else:
                logger.error("Interactive login did not return a token.")
        except Exception as e:
            logger.error(f"An exception occurred during interactive login: {e}")
            return None

    if not token:
        logger.error("Failed to acquire token after all attempts.")

    logger.debug(f"Access Token: {token}")
    return token


def create_client():
    logger.info("Creating CopilotClient...")
    settings = ConnectionSettings(
        environment_id=environ.get("COPILOTSTUDIOAGENT__ENVIRONMENTID"),
        agent_identifier=environ.get("COPILOTSTUDIOAGENT__SCHEMANAME"),
        cloud=None,
        copilot_agent_type=None,
        custom_power_platform_cloud=None,
    )
    logger.debug(f"Using Environment ID: {settings.environment_id}")
    logger.debug(f"Using Agent Schema Name: {settings.agent_identifier}")

    token = acquire_token(
        settings,
        app_client_id=environ.get("COPILOTSTUDIOAGENT__AGENTAPPID"),
        tenant_id=environ.get("COPILOTSTUDIOAGENT__TENANTID"),
    )

    if not token:
        logger.critical("Could not create client because token acquisition failed. Exiting.")
        sys.exit(1)

    copilot_client = CopilotClient(settings, token)
    logger.info("CopilotClient created successfully.")
    return copilot_client


async def ainput(string: str) -> str:
    await asyncio.get_event_loop().run_in_executor(
        None, lambda s=string: sys.stdout.write(s + " ")
    )
    return await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)


async def ask_question(copilot_client, conversation_id):
    query = (await ainput("\n>>>: ")).lower().strip()
    if query in ["exit", "quit"]:
        print("Exiting...")
        return
    if query:
        logger.info(f"Sending query to copilot: '{query}'")
        replies = copilot_client.ask_question(query, conversation_id)
        async for reply in replies:
            logger.debug(f"Received reply of type: '{reply.type}'")
            if reply.type == ActivityTypes.message:
                logger.debug(f"Message content: {reply.text}")
                print(f"\n{reply.text}")
                if reply.suggested_actions:
                    logger.debug(f"Suggested actions found: {[action.title for action in reply.suggested_actions.actions]}")
                    for action in reply.suggested_actions.actions:
                        print(f" - {action.title}")
            elif reply.type == ActivityTypes.end_of_conversation:
                logger.info("Received end_of_conversation activity.")
                print("\nEnd of conversation.")
                sys.exit(0)
        # Continue the conversation loop
        await ask_question(copilot_client, conversation_id)


async def main():
    logger.info("Starting application.")
    copilot_client = create_client()
    
    logger.info("Starting a new conversation with the copilot...")
    act = copilot_client.start_conversation(True)
    
    print("\nSuggested Actions: ")
    async for action in act:
        if action.text:
            logger.debug(f"Received initial action with text: {action.text}")
            print(action.text)
    
    logger.info(f"Conversation started with ID: {action.conversation.id}")
    await ask_question(copilot_client, action.conversation.id)


if __name__ == "__main__":
    asyncio.run(main())