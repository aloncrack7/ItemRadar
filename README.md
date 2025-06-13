# ItemRadar
multi-agent AI that reunites city residents with lost items in minutes. Chatbot intake + semantic/visual matching gives instant pickup info.

```mermaid

flowchart TD
    %% ───────────────────────────────
    %%  Agents & Front-end
    %% ───────────────────────────────
    subgraph User_Frontend["📱 User & Front-end"]
        LostUser[("Lost-Item Chatbot<br>(chatbot_agent)")]
        FoundUser[("Lens: Found-Item Uploader<br>(lens_agent)")]
    end

    %% ───────────────────────────────
    %%  Agents Runtime
    %% ───────────────────────────────
    subgraph ADK["🧠 Agent Development Kit (ADK) runtime"]
        LensAgent[["lens_agent<br/>generate embedding → register_found_item"]]
        ChatbotAgent[["chatbot_agent"]]
        MatcherAgent[["matcher_agent"]]
        ReducerAgent[["reducer_agent"]]
        FilterAgent[["filter_agent"]]
        AnalyticsAgent[["analytics_agent"]]
    end

    %% ───────────────────────────────
    %%  Managed GCP back-ends
    %% ───────────────────────────────
    subgraph GCP["☁️ Google Cloud"]
        Firestore[(Firestore<br/>found_items & lost_reports)]
        ME[(Vertex AI Matching Engine<br/>item_embeddings index)]
        BQ[(BigQuery<br/>match_events)]
        SA[(Service Account<br/>roles: aiplatform.user, datastore.user, bigquery.dataEditor)]
        Secret[("Secret Manager<br/>SA key")]
    end

    %% ───────────────────────────────
    %%  Flow lines
    %% ───────────────────────────────
    FoundUser -->|photo + description| LensAgent
    LensAgent -->|generate embedding| ME
    LensAgent -->|metadata (doc)| Firestore

    LostUser --> ChatbotAgent
    ChatbotAgent --> MatcherAgent
    MatcherAgent -->|find_neighbors| ME
    MatcherAgent -->|candidates| ReducerAgent
    ReducerAgent -->|question| ChatbotAgent
    ChatbotAgent -->|answer| FilterAgent
    FilterAgent -->|filtered list| ReducerAgent
    FilterAgent -->|match found| ChatbotAgent

    ChatbotAgent -->|log| BQ
    LensAgent -->|log| BQ

    SA --> GCP
    Secret --> SA

    classDef agent fill:#fdf6e3,stroke:#657b83,stroke-width:1px;
    classDef gcp fill:#e7f2ff,stroke:#2b76d4,stroke-width:1px;
    class LensAgent,ChatbotAgent,MatcherAgent,ReducerAgent,FilterAgent,AnalyticsAgent agent;
    class Firestore,ME,BQ,gcp gcp;
