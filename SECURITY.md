# Security

Please report security issues privately to the repository owner rather than opening a public issue with exploit details.

CleanRoom executes user-supplied commands in temporary directories. Commands are not run through a shell. The tool can still execute arbitrary programs because its purpose is to observe those programs; use it only with commands you trust.

CleanRoom does not upload workspace contents or contact a network service.
