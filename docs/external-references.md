# External References

- EUMDAC guide: https://user.eumetsat.int/resources/user-guides/eumetsat-data-access-client-eumdac-guide
- EUMDAC package: https://anaconda.org/channels/Eumetsat/packages/eumdac/overview
- EUMDAC PyPI package: https://pypi.org/project/eumdac/
- European Weather Cloud: https://www.europeanweather.cloud/
- EWC OpenStack API access: https://confluence.ecmwf.int/display/EWCLOUDKB/EWC+OpenStack+API+access+-+How+to+request+Openstack+Application+Credentials
- EWC DNS: https://confluence.ecmwf.int/display/EWCLOUDKB/EWC+DNS
- EWCCLI source: https://github.com/ewcloud/ewccli
- EWCCLI package: https://pypi.org/project/ewccli/
- EWC Community Hub catalogue: https://github.com/ewcloud/ewc-community-hub
- Firecube documentation: https://eumetsat.github.io/firecube/latest/
- Firecube API reference: https://eumetsat.github.io/firecube/latest/reference/
- Firecube source and issues: https://github.com/eumetsat/firecube
- Firecube package: https://pypi.org/project/firecube/
- Firecube quickstart example plugin: https://github.com/eumetsat/firecube-quickstart-plugin
- Firecube MTG FCI L1C plugin: https://github.com/eumetsat/firecube-mtg-fci-l1c
- Codex skills: https://developers.openai.com/codex/skills
- VS Code Agent Skills: https://code.visualstudio.com/docs/agent-customization/agent-skills
- Claude Code skills: https://code.claude.com/docs/en/skills
- OpenCode skills: https://opencode.ai/docs/skills/
- Feature DB Python client: https://gitlab.eumetsat.int/usc-feature-detection/earth-system-feature-db-client

The ESF MCP service is internal to EUMETSAT: there is no public request channel for access yet, and
the endpoint and credentials come only from the service administrator. The Feature Database Python
client above is a public package; the Feature Database service it talks to is internal in the same
way, with the API endpoint and API key coming only from the service administrator. Without access, the
corresponding skill explains this and stops.
