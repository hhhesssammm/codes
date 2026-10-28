# Upstream resources

The approved Phase 2 reproducibility ZIP is preserved without modification.
Its contents retain the original source provenance and data-access limitations.
Including audit metadata does not grant new rights to redistribute NSD images,
COCO source photographs or third-party decoder outputs. This release downloads
the needed public caption files and authorized crop images on the user's own
machine; it does not bundle the downloaded images or full caption corpus.

The public `o200k_base` tokenizer data is included solely to make local token
counting and tests independent of another tokenizer download:

- Source: https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken
- Local file: `assets/tokenizer_cache/fb374d419588a4632f3f557e76b4b70aebbca790`
- SHA-256: `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`
- tiktoken repository: https://github.com/openai/tiktoken
- Included upstream MIT license: `third_party/tiktoken_LICENSE.txt`

Dependency licenses remain with their respective packages. No bundled data is
being represented as newly created research data or as unrestricted material.
