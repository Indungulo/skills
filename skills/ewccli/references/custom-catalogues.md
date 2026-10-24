# EWCCLI Custom Catalogues

Use this reference when a user wants to test, write, or deploy an EWC Community Hub item that is not in the official catalogue.

## Command Pattern

Use `--path-to-catalog` at the `hub` group level:

```bash
ewc hub --path-to-catalog <path-to-catalog.yaml> list
ewc hub --path-to-catalog <path-to-catalog.yaml> show <item>
ewc hub --path-to-catalog <path-to-catalog.yaml> deploy <item> --dry-run
```

`--path-to-catalog` expects a file, not a directory.

## Minimal Catalogue Shape

The upstream README shows this structure:

```yaml
apiVersion: communityhub.europeanweather.cloud/v1alpha1
kind: CommunityHubCatalog
spec:
  items:
    my-test-item:
      name: "my-test-item"
      version: "0.0.1"
      description: |
        My first item in EWC Community Hub
      ewccli:
        pathToRequirementsFile: path_to_your_requirements_file
        pathToMainFile: path_to_your_main_ansible_playbook_file
        publicIP: true
        inputs:
          - name: mymandatoryinput
            description: "Required value"
            type: str
      home: https://github.com/your-repo
      sources:
        - https://github.com/your-repo.git
      maintainers:
        - name: your name or org
          email: youremail
          url: https://github.com/your-repo/issues
      icon: https://raw.githubusercontent.com/ewcloud/ewc-community-hub/refs/heads/main/logos/EWCLogo.png
      annotations:
        technology: "Ansible Playbook"
        category: "Test Item"
        supportLevel: "Community"
        licenseType: "Apache License 2.0"
        others: "Deployable,EWCCLI-compatible"
      displayName: My First EWC Community Hub item
      summary: My test item
      license: https://github.com/your-repo/blob/main/LICENSE
      published: true
```

Verify the current metadata requirements against the official EWC Community Hub repository before finalizing new items.

## Source Rules

The upstream README says `sources` can include:

- A public repository URL, for example `https://github.com/your-repo.git`.
- An absolute path to a local directory for experimental local item deployment.

For local paths, ensure the path points to an existing non-empty directory. Do not use user-private paths in committed examples.

## Item Entrypoints

For Ansible Playbook items:

- `ewccli.pathToRequirementsFile` is relative to the source directory or repository.
- `ewccli.pathToMainFile` is relative to the source directory or repository.
- `ewccli.publicIP` controls whether deployment requests a public IP.
- `ewccli.inputs` defines user-provided inputs.

Mandatory inputs omit `default`. Optional inputs include `default`.

## Validation Flow

Use this order:

1. Parse the YAML with a YAML parser.
2. Run:

```bash
ewc hub --path-to-catalog <path-to-catalog.yaml> list
ewc hub --path-to-catalog <path-to-catalog.yaml> show <item>
```

3. Run a deployment dry-run before live deployment:

```bash
ewc hub --path-to-catalog <path-to-catalog.yaml> deploy <item> --dry-run
```

4. Confirm profile, target federee, inputs, public IP, and resource impact before a real deploy.

## Common Mistakes

- Putting `--path-to-catalog` after `deploy`; it belongs to `ewc hub`.
- Using a directory as catalogue path.
- Missing `spec.items`.
- Missing deployable annotations.
- Using a private repository URL that the deployment environment cannot clone.
- Forgetting required `--item-inputs` values.
