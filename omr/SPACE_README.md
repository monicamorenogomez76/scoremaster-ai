---
title: ScoreMaster OMR
emoji: 🎼
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# ScoreMaster OMR

Lector de partituras en PDF de ScoreMaster: convierte cada página en MusicXML con
[copista-2m](https://huggingface.co/kobimusic/copista-2m) ([copisteria](https://github.com/kobimusic/copisteria),
Apache 2.0) y une las páginas en una obra.

Es un servicio privado: Hugging Face solo deja pasar a quien trae un token de la cuenta, y el servicio pide además su
propio secreto `OMR_TOKEN` en la cabecera `X-OMR-Token`. Los PDF se borran al terminar
la lectura y el resultado se olvida en cuanto ScoreMaster lo recoge, o una hora después. El código está en
`omr/` del repositorio de ScoreMaster.
