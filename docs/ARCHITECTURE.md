# Architecture

The pure domain engine receives claims and provenance-bearing operational events
and returns immutable determinations. Fixture generation is deterministic.
SQLite stores each determination, FastAPI queries those stored rows and emits
exports, and React only renders API values. This prevents UI/API/export total
drift and keeps money as Decimal until decimal-string serialization.
