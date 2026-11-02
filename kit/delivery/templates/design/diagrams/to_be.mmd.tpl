flowchart LR
  SRC[Source / ingestion] --> LND[({{WORK_USER}}.{{LANDING_TABLE}})]
  LND --> VAR[ODI variables]
  VAR --> PKG[{{PACKAGE_NAME}}]
  PKG --> TGT[({{WORK_USER}} targets)]
