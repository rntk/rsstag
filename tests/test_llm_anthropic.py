"""Comprehensive unit tests for rsstag.llm.anthropic.Anthropic."""

import unittest
from unittest.mock import MagicMock, patch

from rsstag.llm.anthropic import Anthropic
from rsstag.llm.base import LLMResponse, ToolCall, ToolDefinition


class TestAnthropicInit(unittest.TestCase):
    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_valid_model(self, mock_anthropic_cls: MagicMock) -> None:
        client = Anthropic(token="tok", model="claude-3-5-sonnet-20241022")

        self.assertEqual(client._Anthropic__model, "claude-3-5-sonnet-20241022")
        mock_anthropic_cls.assert_called_once_with(
            api_key="tok",
            timeout=300.0,
            max_retries=0,
        )

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_invalid_model_falls_back_to_first_allowed(self, mock_anthropic_cls: MagicMock) -> None:
        client = Anthropic(token="tok", model="not-a-model")

        self.assertEqual(client._Anthropic__model, Anthropic.ALLOWED_MODELS[0])
        mock_anthropic_cls.assert_called_once_with(
            api_key="tok",
            timeout=300.0,
            max_retries=0,
        )

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_custom_timeout(self, mock_anthropic_cls: MagicMock) -> None:
        Anthropic(token="tok", timeout=60.0)

        mock_anthropic_cls.assert_called_once_with(
            api_key="tok",
            timeout=60.0,
            max_retries=0,
        )

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_custom_retry_limit(self, mock_anthropic_cls: MagicMock) -> None:
        Anthropic(token="tok", max_retries=1)

        mock_anthropic_cls.assert_called_once_with(
            api_key="tok",
            timeout=300.0,
            max_retries=1,
        )


class TestAnthropicCall(unittest.TestCase):
    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_success_returns_text(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello world")]
        mock_client.messages.create.return_value = mock_response

        client = Anthropic(token="tok")
        result = client.call(["How are you?"])

        mock_client.messages.create.assert_called_once_with(
            model=client._Anthropic__model,
            max_tokens=Anthropic.DEFAULT_MAX_TOKENS,
            messages=[{"role": "user", "content": "How are you?"}],
        )
        self.assertEqual(result, "Hello world")

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_error_returns_string(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API down")

        client = Anthropic(token="tok")
        result = client.call(["Hello"])

        self.assertTrue(result.startswith("Anthropic error"))
        self.assertIn("API down", result)


class TestAnthropicCallWithTools(unittest.TestCase):
    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_with_no_tools_omits_tools_parameter(
        self, mock_anthropic_cls: MagicMock
    ) -> None:
        mock_client: MagicMock = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response: MagicMock = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Final report")]
        mock_client.messages.create.return_value = mock_response

        client = Anthropic(token="tok")
        result: LLMResponse = client.call_with_tools(
            user_msgs=["Finish"], tools=[]
        )

        self.assertEqual(result.content, "Final report")
        kwargs = mock_client.messages.create.call_args.kwargs
        self.assertNotIn("tools", kwargs)

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_with_tools_text_response(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="All good")]
        mock_client.messages.create.return_value = mock_response

        client = Anthropic(token="tok")
        tools = [ToolDefinition(name="t1", description="d1")]
        result = client.call_with_tools(user_msgs=["Hello"], tools=tools)

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.content, "All good")
        self.assertEqual(result.tool_calls, ())
        self.assertIs(result.raw, mock_response)

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_with_tools_tool_use_response(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.id = "call_1"
        mock_block.name = "t1"
        mock_block.input = {"arg": "val"}
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        client = Anthropic(token="tok")
        tools = [ToolDefinition(name="t1", description="d1")]
        result = client.call_with_tools(user_msgs=["Hello"], tools=tools)

        self.assertIsInstance(result, LLMResponse)
        self.assertIsNone(result.content)
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].id, "call_1")
        self.assertEqual(result.tool_calls[0].name, "t1")
        self.assertEqual(result.tool_calls[0].arguments, {"arg": "val"})

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_with_tools_error_returns_llm_response(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("Boom")

        client = Anthropic(token="tok")
        result = client.call_with_tools(user_msgs=["Hello"], tools=[])

        self.assertIsInstance(result, LLMResponse)
        self.assertTrue(result.content.startswith("Anthropic error"))
        self.assertIn("Boom", result.content)

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_with_tools_full_kwargs(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="OK")]
        mock_client.messages.create.return_value = mock_response

        client = Anthropic(token="tok")
        tools = [ToolDefinition(name="t1", description="d1", parameters={"type": "object"})]
        client.call_with_tools(
            user_msgs=["u1"],
            tools=tools,
            system_msgs=["Be helpful"],
            messages=[
                {"role": "user", "content": "m1"},
                {"role": "user", "content": "m2"},
                {"role": "assistant", "content": "a1"},
            ],
            max_tokens=1024,
        )

        kwargs = mock_client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], client._Anthropic__model)
        self.assertEqual(kwargs["max_tokens"], 1024)
        self.assertEqual(kwargs["system"], "Be helpful")
        # Consecutive user messages are merged
        self.assertEqual(kwargs["messages"], [
            {"role": "user", "content": "m1\nm2"},
            {"role": "assistant", "content": "a1"},
        ])
        self.assertEqual(kwargs["tools"], [
            {"name": "t1", "description": "d1", "input_schema": {"type": "object"}}
        ])


class TestAnthropicBuildMessages(unittest.TestCase):
    def test_build_messages_from_user_msgs(self) -> None:
        result, system = Anthropic._build_messages(["msg1", "msg2"], None, None)

        self.assertEqual(result, [
            {"role": "user", "content": "msg1"},
            {"role": "user", "content": "msg2"},
        ])
        self.assertEqual(system, [])

    def test_build_messages_with_system_msgs(self) -> None:
        result, system = Anthropic._build_messages(["msg1"], None, ["sys1"])

        self.assertEqual(result, [{"role": "user", "content": "msg1"}])
        self.assertEqual(system, ["sys1"])

    def test_build_messages_empty_list_uses_user_msgs(self) -> None:
        result, system = Anthropic._build_messages(["msg1"], [], ["sys1"])

        self.assertEqual(result, [{"role": "user", "content": "msg1"}])
        self.assertEqual(system, ["sys1"])

    def test_build_messages_extracts_system(self) -> None:
        messages = [
            {"role": "system", "content": "sys1"},
            {"role": "user", "content": "hello"},
        ]
        result, system = Anthropic._build_messages([], messages, None)

        self.assertEqual(result, [{"role": "user", "content": "hello"}])
        self.assertEqual(system, ["sys1"])

    def test_build_messages_normalizes_tool_results(self) -> None:
        messages = [
            {"role": "tool", "name": "my_tool", "content": "result"},
        ]
        result, system = Anthropic._build_messages([], messages, None)

        self.assertEqual(result, [{"role": "user", "content": "Tool result from my_tool:\nresult"}])
        self.assertEqual(system, [])

    def test_build_messages_tool_defaults_name(self) -> None:
        messages = [
            {"role": "tool", "content": "result"},
        ]
        result, system = Anthropic._build_messages([], messages, None)

        self.assertEqual(result, [{"role": "user", "content": "Tool result from tool:\nresult"}])

    def test_build_messages_empty_role_defaults_to_user(self) -> None:
        messages = [
            {"role": "   ", "content": "hello"},
        ]
        result, system = Anthropic._build_messages([], messages, None)

        self.assertEqual(result, [{"role": "user", "content": "hello"}])

    def test_build_messages_none_content_becomes_empty_string(self) -> None:
        messages = [
            {"role": "user", "content": None},
        ]
        result, system = Anthropic._build_messages([], messages, None)

        self.assertEqual(result, [{"role": "user", "content": ""}])


class TestAnthropicToProviderTools(unittest.TestCase):
    def test_to_provider_tools(self) -> None:
        tools = [
            ToolDefinition(
                name="tool1",
                description="desc1",
                parameters={"type": "object", "properties": {}},
            ),
        ]
        result = Anthropic._to_provider_tools(tools)

        self.assertEqual(result, [
            {
                "name": "tool1",
                "description": "desc1",
                "input_schema": {"type": "object", "properties": {}},
            }
        ])

    def test_to_provider_tools_empty_parameters(self) -> None:
        tools = [ToolDefinition(name="tool1", description="desc1")]
        result = Anthropic._to_provider_tools(tools)

        self.assertEqual(result, [
            {"name": "tool1", "description": "desc1", "input_schema": {}}
        ])


class TestAnthropicMergeConsecutiveRoles(unittest.TestCase):
    def test_merge_string_content(self) -> None:
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "user", "content": "world"},
        ]
        result = Anthropic._merge_consecutive_roles(messages)

        self.assertEqual(result, [{"role": "user", "content": "hello\nworld"}])

    def test_merge_list_content(self) -> None:
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
            {"role": "user", "content": [{"type": "text", "text": "world"}]},
        ]
        result = Anthropic._merge_consecutive_roles(messages)

        self.assertEqual(result, [
            {"role": "user", "content": [
                {"type": "text", "text": "hello"},
                {"type": "text", "text": "world"},
            ]}
        ])

    def test_merge_list_with_string(self) -> None:
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
            {"role": "user", "content": "world"},
        ]
        result = Anthropic._merge_consecutive_roles(messages)

        self.assertEqual(result, [
            {"role": "user", "content": [
                {"type": "text", "text": "hello"},
                {"type": "text", "text": "world"},
            ]}
        ])

    def test_no_merge_different_roles(self) -> None:
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = Anthropic._merge_consecutive_roles(messages)

        self.assertEqual(result, [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ])

    def test_preserves_originals(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        result = Anthropic._merge_consecutive_roles(messages)

        self.assertIsNot(result[0], messages[0])

    def test_empty_list(self) -> None:
        result = Anthropic._merge_consecutive_roles([])

        self.assertEqual(result, [])


class TestAnthropicFromProviderResponse(unittest.TestCase):
    def test_from_text_response(self) -> None:
        response = MagicMock()
        response.content = [MagicMock(type="text", text="Hello")]
        result = Anthropic._from_provider_response(response)

        self.assertEqual(result.content, "Hello")
        self.assertIsNone(result.reasoning)
        self.assertEqual(result.tool_calls, ())
        self.assertIs(result.raw, response)

    def test_from_thinking_response(self) -> None:
        response = MagicMock()
        response.content = [MagicMock(type="thinking", thinking="Deep thought")]
        result = Anthropic._from_provider_response(response)

        self.assertIsNone(result.content)
        self.assertEqual(result.reasoning, "Deep thought")

    def test_from_tool_use_response(self) -> None:
        response = MagicMock()
        block = MagicMock()
        block.type = "tool_use"
        block.id = "t1"
        block.name = "tool1"
        block.input = {"a": 1}
        response.content = [block]
        result = Anthropic._from_provider_response(response)

        self.assertIsNone(result.content)
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0], ToolCall(id="t1", name="tool1", arguments={"a": 1}))

    def test_from_multiple_blocks(self) -> None:
        response = MagicMock()
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "t1"
        tool_block.name = "tool1"
        tool_block.input = {}
        response.content = [
            MagicMock(type="thinking", thinking="Reason"),
            MagicMock(type="text", text="Part 1"),
            MagicMock(type="text", text="Part 2"),
            tool_block,
        ]
        result = Anthropic._from_provider_response(response)

        self.assertEqual(result.content, "Part 1\nPart 2")
        self.assertEqual(result.reasoning, "Reason")
        self.assertEqual(len(result.tool_calls), 1)

    def test_from_missing_attributes(self) -> None:
        response = MagicMock()
        block = MagicMock()
        # block has no 'type' attribute
        del block.type
        response.content = [block]
        result = Anthropic._from_provider_response(response)

        self.assertIsNone(result.content)
        self.assertIsNone(result.reasoning)
        self.assertEqual(result.tool_calls, ())

    def test_skips_empty_text(self) -> None:
        response = MagicMock()
        response.content = [
            MagicMock(type="text", text=""),
            MagicMock(type="text", text="Non-empty"),
        ]
        result = Anthropic._from_provider_response(response)

        self.assertEqual(result.content, "Non-empty")

    def test_tool_use_id_fallback_to_empty_string(self) -> None:
        response = MagicMock()
        block = MagicMock()
        block.type = "tool_use"
        block.id = None
        block.name = "tool1"
        block.input = {}
        response.content = [block]
        result = Anthropic._from_provider_response(response)

        self.assertEqual(result.tool_calls[0].id, "")


class TestAnthropicCallCitation(unittest.TestCase):
    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_citation_success(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        block1 = MagicMock(type="text", text="According to doc")
        block1.citations = None
        block2 = MagicMock(type="text", text="the grass is green")
        cite = MagicMock(cited_text="The grass is green.")
        block2.citations = [cite]
        mock_response.content = [block1, block2]
        mock_client.messages.create.return_value = mock_response

        client = Anthropic(token="tok")
        result = client.call_citation("What color?", ["The grass is green."])

        self.assertIn("According to doc", result)
        self.assertIn("the grass is green", result)
        self.assertIn("<citation>The grass is green.</citation>", result)

        kwargs = mock_client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], client._Anthropic__model)
        sent_messages = kwargs["messages"]
        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(sent_messages[0]["role"], "user")
        content = sent_messages[0]["content"]
        self.assertEqual(content[-1], {"type": "text", "text": "What color?"})
        self.assertEqual(content[0]["type"], "document")
        self.assertEqual(content[0]["title"], "Document 0")
        self.assertEqual(content[0]["citations"], {"enabled": True})
        self.assertEqual(content[0]["source"]["data"], "The grass is green.")

    @patch("rsstag.llm.anthropic.anthropic.Anthropic")
    def test_call_citation_error_returns_string(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("Network error")

        client = Anthropic(token="tok")
        result = client.call_citation("What?", ["Doc"])

        self.assertTrue(result.startswith("Anthropic error"))
        self.assertIn("Network error", result)


if __name__ == "__main__":
    unittest.main()
