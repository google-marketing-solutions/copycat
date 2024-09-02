# Copycat - AI Generated Google Search Ad Copy that Matches Your Brand Style

**Disclaimer: This is not an official Google product.**

## Overview

Copycat is a Python package leveraging the power of Google Gemini to generate high-quality Google Search ad copy. Its unique feature is the ability to learn from your existing top-performing ads, ensuring the generated copy aligns seamlessly with your brand voice and guidelines.

Copycat can be used to:

Generate new ads for new lists of keywords you would like to start bidding on.
Expand existing Responsive Search Ads which do not make use of all the headline and description slots.
Edit and improve existing ads. 

## Key Benefits

* **Efficiency:** Quickly generate compelling ad copy for multiple campaigns, saving you valuable time and resources.
* **Quality:** Maintain high standards by producing ad copy that reflects your brand's unique style and messaging.
* **Scalability:** Easily expand your Google Ads reach without compromising on ad quality or brand consistency.

## Quick Start

To get started, just open our Colab notebook here and follow the instructions.

## Important Notes

* Ensure you have a valid Google Cloud Project with the Vertex AI API enabled.
* Copycat will use Gemini via your Google Cloud Project, please be aware that using these cloud services will incur costs. Details on model pricing [here](https://ai.google.dev/pricing)
* Provide a sufficient number of high-quality existing ads for the model to learn effectively.
* Always review and edit the generated ad copy before using it in your campaigns.
* Refer to the Google Ads policies to ensure your ads comply with all guidelines.

## Style Guide

One of the key parts of Copycat is the style guide. When running the notebook you have the option to create a style guide. You can upload brand style documents in pdf and csv to enrich the style guide. The style guide can also be manually changed over time and copycat will use this to create the ad copies in your brands’ style!

## Gemini
This solution uses Google Gemini models on GCP to generate ad copies. Please
review the [terms of service](https://ai.google.dev/gemini-api/terms).

## Citing Copycat

To cite this repository:

```
@software{copycat_github,
  author = {Sam Bailey, Piet Snel, Christiane Ahlheim, Sumedha Menon, Hector Parra, Jaime Martínez, Letizia Bertolaja},
  title = Copycat - AI Generated Google Search Ad Copy that Matches Your Brand Style},
  url = {https://github.com/google-marketing-solutions/copycat},
  version = {0.0.1},
  year = {2024},
}
```

## License

Copyright 2024 Google LLC. This solution, including any related sample code or data, is made available on an "as is", "as available", and "with all faults" basis, solely for illustrative purposes, and without warranty or representation of any kind. This solution is experimental, unsupported and provided solely for your convenience. Your use of it is subject to your agreements with Google, as applicable, and may constitute a beta feature as defined under those agreements. To the extent that you make any data available to Google in connection with your use of the solution, you represent and warrant that you have all necessary and appropriate rights, consents and permissions to permit Google to use and process that data. By using any portion of this solution, you acknowledge, assume and accept all risks, known and unknown, associated with its usage, including with respect to your deployment of any portion of this solution in your systems, or usage in connection with your business, if at all.