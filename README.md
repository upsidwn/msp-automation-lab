# MSP Automation Lab

[![CI](https://github.com/upsidwn/msp-automation-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/upsidwn/msp-automation-lab/actions/workflows/ci.yml)

A collection of practical automation tools, workflows, and AI-assisted solutions designed to improve efficiency, documentation, and consistency within managed service provider environments.

## Overview

Managed Service Providers (MSPs) rely heavily on repeatable processes, accurate documentation, and efficient technician workflows.

This project explores how automation, infrastructure-as-code, and AI-assisted tooling can help reduce repetitive tasks, improve consistency, and allow technicians to focus on higher-value work.

The goal of this project is not to replace technicians, but to create tools that improve operational efficiency and reliability.

## Quick start

Each lab tool has its own README with full setup. Short version:

- [Network inventory collector](lab/network-inventory-collector/README.md): auto-discover a subnet, pull inventory, check firmware compliance.
  ```
  cd lab/network-inventory-collector
  pip install -r source/requirements.txt
  python source/menu.py
  ```
- [Config backup system](lab/config-backup-system/README.md): Ansible playbook, backs up Junos/EXOS configs. Needs vault setup first, see its README.

## Project Goals

- Automate repetitive MSP operational tasks
- Improve network documentation and visibility
- Explore infrastructure-as-code practices
- Develop AI-assisted technician workflows
- Build reusable automation examples using industry tools

See [docs/ROADMAP.md](docs/ROADMAP.md) for the play by play plan and
current status, and [docs/NOTES.md](docs/NOTES.md) for the tech stack and
working standards.

## Status

Active development - currently building the network inventory collector
(Phase 2). Things will move around as I learn.


