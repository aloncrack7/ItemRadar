# ItemRadar
multi-agent AI that reunites city residents with lost items in minutes. Chatbot intake + semantic/visual matching gives instant pickup info.

```mermaid

flowchart TD
    %% ───────── Front-end ─────────
    subgraph User_Frontend["📱 User & Front-end"]
        LostChat[("Lost-Item Chatbot<br/>(chatbot_agent)")]
        FoundUploader[("Lens Uploader<br/>(lens_agent)")]
    end

    %% ───────── ADK runtime ─────────
    subgraph ADK["🧠 ADK runtime"]
        LensAgent["lens_agent"]
        ChatbotAgent["chatbot_agent"]
        MatcherAgent["matcher_agent"]
        ReducerAgent["reducer_agent"]
        FilterAgent["filter_agent"]
        AnalyticsAgent["analytics_agent"]
    end

    %% ───────── GCP services ─────────
    subgraph GCP["☁️ Google Cloud Services"]
        Firestore[(Firestore<br/>found_items / lost_reports)]
        ME[(Vertex AI Matching Engine<br/>item_embeddings)]
        BQ[(BigQuery<br/>match_events)]
    end

    %% ───────── Flow ─────────
    FoundUploader  --> |photo + desc| LensAgent
    LensAgent      --> |embedding|   ME
    LensAgent      --> |metadata|    Firestore

    LostChat       --> ChatbotAgent
    ChatbotAgent   --> MatcherAgent
    MatcherAgent   --> |find_neighbors| ME
    MatcherAgent   --> |candidates|     ReducerAgent
    ReducerAgent   --> |question|       ChatbotAgent
    ChatbotAgent   --> |answer|         FilterAgent
    FilterAgent    --> |filtered list|  ReducerAgent
    FilterAgent    --> |match!|         ChatbotAgent

    LensAgent      --> |log| BQ
    ChatbotAgent   --> |log| BQ

    %% ───────── Styling ─────────
    classDef agent fill:#fdf6e3,stroke:#657b83,stroke-width:1px;
    classDef gcp   fill:#e7f2ff,stroke:#2b76d4,stroke-width:1px;
    class LensAgent,ChatbotAgent,MatcherAgent,ReducerAgent,FilterAgent,AnalyticsAgent agent;
    class Firestore,ME,BQ gcp;

