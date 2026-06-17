# RENINE PROJECT PLAN

Version 1.0

## Overview

Renine is a free, hybrid, local AI butler inspired by Friday from Iron Man. Its purpose is to become an intelligent companion capable of assisting with daily life, home management, productivity, files, coding, spreadsheets, browser tasks, and personal memories.

Renine should feel like she lives with us and understands our environment, routines, personalities, and preferences.

---

# Owners

Primary Owner:

* Efren

Secondary Owner:

* Francine

---

# Goal

Create a Level 5 AI assistant that can:

* Talk naturally through voice and chat.
* Manage the home.
* Understand files and documents.
* Remember important information.
* Control the computer.
* Help with coding.
* Assist with spreadsheet and reporting work.
* Manage pets and schedules.
* Keep track of ingredients and household supplies.
* Use browser agents.
* Maintain long-term memories.
* Continue growing over time.

---

# Hardware

CPU:
Ryzen 5 5600X

GPU:
RTX 3060 12GB

RAM:
16GB

Operating System:
Windows 11

---

# Architecture

Human
↓
Wake Word ("Renine")
↓
Speech-To-Text
↓
Router
↓
Main Brain
↓
Tool Calling System
↓
Memory + Databases + Agents
↓
Response
↓
Text-To-Speech

---

# Main Models

## Main Brain

Qwen3 8B

Purpose:

* Reasoning
* Conversations
* Tool calling
* General intelligence

---

## Speech-To-Text

Faster Whisper

Purpose:

* Convert speech into text

---

## Text-To-Speech

Piper TTS

Purpose:

* Voice responses

---

## Vision Model

Qwen2.5-VL

Purpose:

* Screenshots
* OCR
* Image understanding
* Webcam support

---

## Embedding Model

BGE-M3

Purpose:

* Memory retrieval

---

## Vector Database

ChromaDB

Purpose:

* Long-term memory search

---

## Workflow Framework

LangGraph

Purpose:

* Agent orchestration
* Tool execution

---

# Personality

Inspired by Friday.

Traits:

* Calm
* Intelligent
* Friendly
* Helpful
* Professional
* Light humor
* Caring
* Not overly emotional

---

# Memory System

Renine has four memory layers.

---

## Layer 1

Current Conversation

Purpose:

Temporary context during active conversations.

Characteristics:

* Exists only while conversation is active.
* Used for understanding current discussion.
* Automatically discarded after conversation ends.

---

## Layer 2

Conversation History Memory

Purpose:

Stores important information from conversations.

Characteristics:

* Important messages are summarized.
* Stored as history.
* Retained for two days.
* Deleted automatically after expiration.
* Allows Renine to recall recent discussions.

Example:

June 17:

* Discussed project architecture.
* Talked about groceries.
* Planned vacation.

June 18:

* Added new pet information.

---

## Layer 3

Mind Database

Purpose:

Permanent long-term memory.

This layer represents Renine's mind.

Nothing inside this database should ever be sent to cloud services.

Examples:

Food inventory

Bills

Electricity usage

Schedules

Pets

Medicine

House updates

Room information

Appliances

Furniture

Technology

Devices

Passwords (optional and encrypted)

Birthdays

Important dates

Meeting schedules

Notes

Tasks

Projects

Files

Emails

Daily routines

Ingredient quantities

Shopping lists

Pet feeding schedules

Calendar events

Everything important about the house and life.

---

## Layer 4

Personality Database

Purpose:

Store information about people.

Examples:

Names

Ages

Favorites

Personality types

Likes

Dislikes

Hobbies

Relationships

Birthdays

Food preferences

Habits

Dreams

Goals

Pets

Family members

Friends

This layer helps Renine understand who we are.

---

# Agents

Renine should use a multi-agent architecture.

---

## Main Brain Agent

Responsibilities:

* Conversations
* Planning
* Delegation

---

## Memory Agent

Responsibilities:

* Store memories
* Retrieve memories
* Organize information

---

## House Agent

Responsibilities:

* House information
* Appliances
* Rooms
* Furniture

---

## Inventory Agent

Responsibilities:

* Food inventory
* Ingredient quantities
* Supplies

Example:

Question:

"What can we cook?"

Renine checks inventory and gives suggestions.

---

## Pet Agent

Responsibilities:

* Pet names
* Feeding schedules
* Medicine
* Vaccines

---

## Calendar Agent

Responsibilities:

* Events
* Meetings
* Reminders
* Alarms
* Timers

---

## Email Agent

Responsibilities:

* Gmail
* Notifications
* Drafting replies

---

## Browser Agent

Responsibilities:

* Research
* Shopping
* Forms
* Automation

---

## File Agent

Responsibilities:

* Search files
* Read PDFs
* Organize folders

---

## Coding Agent

Responsibilities:

* Programming
* Debugging
* VS Code integration

---

## Spreadsheet Agent

Responsibilities:

* Excel
* Dashboards
* Reports
* CSV files

---

## Vision Agent

Responsibilities:

* Screenshots
* OCR
* Images
* Webcam understanding

---

## Smart Home Agent

Responsibilities:

* Lights
* Sensors
* Devices

---

## News Agent

Responsibilities:

* Headlines
* Current events

---

# Interfaces

## Desktop Application

Main interface.

Capabilities:

* Chat
* Voice conversations

---

## Sidebar

Always accessible.

Similar to Copilot.

---

## Floating Assistant

Small widget.

Quick access.

---

## Voice Mode

Wake word:

"Renine"

Example:

"Renine, open Excel."

---

## Future Mobile Application

Remote access.

Home management while away.

---

# Functions

System control

File management

Coding

Spreadsheet analysis

Browser research

Planning

Calendar

Timers

Alarms

News

Media control

Vision

OCR

Pet management

House management

Ingredient management

Shopping assistance

Email support

Meeting management

Daily summaries

Personal notes

Task management

Knowledge retrieval

---

# Security

Sensitive information should remain local.

Mind database should never be shared with cloud APIs.

Hybrid mode is allowed.

External AI services may be used only for difficult tasks, but confidential memories remain private.

---

# Project Structure

Renine/

brain/

memory/

house_database/

personality_database/

conversation_history/

agents/

voice/

vision/

tools/

calendar/

email/

browser/

smart_home/

pets/

inventory/

files/

coding/

spreadsheet/

ui/

sidebar/

floating_widget/

mobile/

models/

config/

logs/

tests/

---

# Development Roadmap

Phase 1

MVP

* Chat interface
* Voice
* Qwen3
* Wake word

---

Phase 2

Memory system

* Layer 1
* Layer 2
* Layer 3
* Layer 4

---

Phase 3

Personal databases

* Family
* Favorites
* Pets
* Ingredients

---

Phase 4

Desktop control

* Apps
* Files
* System functions

---

Phase 5

Vision

* OCR
* Screenshots
* Webcam

---

Phase 6

Browser agent

* Research
* Shopping
* Forms

---

Phase 7

Smart home integration

---

Phase 8

Mobile companion

---

Phase 9

Level 5 Renine

Continuous learning.

Natural conversations.

Multiple interfaces.

House management.

Personal memory.

Daily assistance.

An AI that truly feels like a member of the family.

End of File.
