<p align="center">
  <img src="assets/prism-logo.png" width="140" alt="PRISM OS">
</p>

<h1 align="center">PRISM OS</h1>

<p align="center">
  <strong>Pi Remote &amp; Integrated Screen Manager</strong><br>
  Designed for reliable media, display and TV control.
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/status-early%20development-orange" alt="Status"></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-Raspberry%20Pi-red" alt="Platform"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python"></a>
  <a href="#"><img src="https://img.shields.io/badge/license-TBD-lightgrey" alt="License"></a>
</p>

## About

**PRISM** is a planned lightweight operating system for Raspberry Pi, initially targeting the **Raspberry Pi Zero 2 W**.

The goal is to turn a Raspberry Pi into a reliable appliance for:

* Media playback
* HDMI / CEC TV control
* Remote content and commands
* Simple terminal-based configuration
* Automatic recovery and reliable operation

> **A Raspberry Pi that behaves like an appliance, not a desktop.**

## Concept

```mermaid
flowchart LR
    Server["Remote Server"]
    Pi["PRISM OS"]
    TV["TV / Display"]

    Server -->|Content & Control| Pi
    Pi -->|HDMI / CEC| TV
```

The Pi is intended to handle playback and TV control, while an external server can determine what should be displayed.

