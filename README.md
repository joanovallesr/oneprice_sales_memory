# OnePrice Sales Memory - vCon MCP Sales Assistant

**VCONIC TADHack Entry** | Built by Joan Ovalles, Mullinax Ford Salesperson

Turns scattered car leads (web forms, calls, showroom) into **prioritized action items** using **VCON MCP** + AI analysis.

[![FastMCP](https://img.shields.io/badge/FastMCP-3.1.0-brightgreen)](https://gofastmcp.com)
[![VCON MCP](https://img.shields.io/badge/VCON%20MCP-2026.02.27-blue)](https://mcp.conserver.io)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)

## **Problem**

OnePrice salespeople get **40+ leads/day** across:
- Web forms (Autotrader, Cars.com)
- Phone calls  
- Showroom walk-ins

**90% forgotten** → lost deals. Need:
- "Who to call **NOW**?"
- "What exactly to say?"

## **Solution**

**vCon MCP** unifies conversations → **this MCP server** creates/tags/analyzes/searches → **AI surfaces hot leads + scripts**.

**7 MCP Tools**:
| Tool | Purpose |
|------|---------|
| `create_oneprice_lead_vcon` | New lead vCon (web/phone/showroom) |
| `analyze_and_tag_vcon` | AI classification (funnel/urgency/tags) |
| `add_followup_vcon` | Record follow-up call/note |
| `get_hot_leads` | Hot leads needing follow-up |
| `get_missed_leads` | New leads with no follow-up |
| `search_by_intent` | Semantic search ("payment under $600") |
| `generate_followup` | Mullinax-style sales scripts |

## **Live Demo** (90 seconds)

```
1. docker run vcon-mcp (10s)
2. python mullinax_sales_server.py (5s)
3. Claude/Cursor:
   create_oneprice_lead_vcon("Jane", "Explorer $600/mo", "web_lead")
   analyze_and_tag_vcon("uuid") → {"urgency": "hot_lead"}
   get_hot_leads(2) → [{"name": "Jane", "no_followup": true}]
   generate_followup("Jane") → "Hi Jane, Explorer $599 OTD..."
```

**[Demo Video](https://github.com/user-uploads/demo.mp4)**

## **Quick Start**

```bash
# 1. Clone
git clone https://github.com/joanovalles/mullinax-sales-memory
cd mullinax-sales-memory

# 2. Install
pip install -r requirements.txt

# 3. Setup (get your OpenAI key: platform.openai.com/api-keys)
cp .env.example .env
# Edit .env → OPENAI_API_KEY=sk-...

# 4. VCON MCP (Docker)
docker run -d -p 3000:3000 public.ecr.aws/r4g1k2s3/vcon-dev/vcon-mcp:main

# 5. Run MCP server
source .env && python mullinax_sales_server.py
```

**Connect to Claude Desktop/Cursor/ChatGPT** (see `~/.cursor/mcp.json` example).

## **Architecture**

```
Claude/Cursor ── MCP ── mullinax_sales_server.py ── vcon_client.py ── VCON MCP
                                                      │
                                                      └── OpenAI (analyze/generate)
```

- **Clean separation**: MCP server → VCON wrapper → OpenAI analysis
- **Production-ready**: Pydantic types, async, error handling
- **vCon-native**: `create_vcon_from_template`, `add_analysis`, `add_tag`, hybrid search

## **vCon Schema (Car Sales)**

```
Parties: [{"role": "customer", "name": "Jane"}, {"role": "agent", "name": "Joan"}]
Tags: funnel_stage=new_lead, urgency=hot_lead, payment_sensitive=true
Analysis: {"vehicle_interest": "Explorer", "timeline": "2_weeks"}
```

## **TADHack Highlights**

- **Sponsor APIs**: Full VCON MCP (CRUD, search, tags, analysis)
- **Real use case**: Real dealership lead chaos → AI-powered pipeline
- **Production code**: Types, tests, docs, error handling
- **Multi-client**: Works with Claude, Cursor, ChatGPT MCP
- **Scalable**: Add Supabase → persistent vCons across dealerships

## **Files**

```
├── oneprice_sales_server.py  # 7 MCP tools
├── vcon_client.py           # VCON MCP wrapper
├── analysis.py              # OpenAI classification/scripts
├── models.py                # Pydantic types
├── config.py                # Env loading
├── sample_data/             # Real Mullinax leads
├── requirements.txt         # pip install
└── README.md                # This file
```

## **Acknowledgments**

- **VCONIC/Strolid** - MCP server + vCon standard
- **FastMCP** - Python MCP framework  
- **OpenAI** - Lead analysis + follow-up generation

**Built for TADHack March 7-8, 2026** by Joan Ovalles (joanovalles.com)

---

**Star this repo** | **Follow @joanovallesr**
```

**Star this repo** | **Follow @joanovallesr
