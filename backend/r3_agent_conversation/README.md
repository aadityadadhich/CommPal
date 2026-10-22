# Role 3: Agent & Conversation Lead (R3)
**Scope:** Conversational agent loop, Google Gemini client with function calling, sandboxed tool definitions, clarification policy, explanation generation, and prompt injection defenses.  
**Ownership Boundary (SRDD 7.2):** The agent never calls merchant adapters directly and has NO access to wallet credentials, mandate rules, or approval overrides. It only calls sandboxed tools (`request_purchase`, `set_stock`, `list_items`, `compare_offers`).
