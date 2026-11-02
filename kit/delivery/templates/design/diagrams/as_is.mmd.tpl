flowchart LR
  SRC[Source / ingestion] --> LND[({{LANDING_TABLE}})]
  LND --> BLD[Blendata: {{WORKFLOW}}]
  BLD --> TGT[(Target tables)]
