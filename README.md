# PAIC Python Starter

## Setup

- `git remote remove origin`
- `git remote add origin <your-repo-url>`
- `cp .env.sample .env`
  - Update with your keys
- `uv sync`
- `uv run python main.py`
- Start AI Coding!

## aiden

- `cp .template.aiden.conf.yml .aiden.conf.yml`
  - Update to fit your needs

## PAIC tooling

### Specs

- `aiden`
- `/editor`
- paste in your spec from `specs/`

### ADWs 

- `uv run python adw/adw_bump_version.template.py`
  - use this as a template for your own ADWs
  - review this before you use it

### Director

- `uv run python director.py --config spec/*.yaml`
  - use the `director_template.example.yaml` as a template for director configs
