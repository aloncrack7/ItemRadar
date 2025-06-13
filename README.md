# ItemRadar
multi-agent AI that reunites city residents with lost items in minutes. Chatbot intake + semantic/visual matching gives instant pickup info.

```mermaid

flowchart TD
    %% ─────── Front-end ───────
    subgraph User["📱 User Front-end"]
        LostChat[("Lost-Item Chatbot<br/>(chatbot_agent)")]
        FoundUp[("Lens Uploader<br/>(lens_agent)")]
    end

    %% ─────── ADK runtime ───────
    subgraph ADK["🧠 ADK runtime"]
        LensA["lens_agent"]
        ChatA["chatbot_agent"]
        MatchA["matcher_agent"]
        RedA["reducer_agent"]
        FilA["filter_agent"]
        AnaA["analytics_agent"]
    end

    %% ─────── GCP services ───────
    subgraph GCP["☁️ Google Cloud"]
        FS[(Firestore<br/>found_items / lost_reports)]
        ME[(Vertex AI Matching Engine<br/>item_embeddings)]
        BQ[(BigQuery<br/>match_events)]
    end

    %% ─────── Flows ───────
    FoundUp  -->|photo + desc|  LensA
    LensA    -->|embedding|     ME
    LensA    -->|metadata|      FS

    LostChat --> ChatA
    ChatA    --> MatchA
    MatchA   -->|find_neighbors| ME
    MatchA   -->|candidates|     RedA
    RedA     -->|question|       ChatA
    ChatA    -->|answer|         FilA
    FilA     -->|filtered|       RedA
    FilA     -->|match found|    ChatA

    LensA    -->|log| BQ
    ChatA    -->|log| BQ

    %% Styling
    classDef agent fill:#fdf6e3,stroke:#657b83,stroke-width:1px;
    classDef gcp   fill:#e7f2ff,stroke:#2b76d4,stroke-width:1px;
    class LensA,ChatA,MatchA,RedA,FilA,AnaA agent;
    class FS,ME,BQ gcp;


