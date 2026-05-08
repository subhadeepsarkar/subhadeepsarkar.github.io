---
layout: page
permalink: /publications/
title: Publications
description: in reversed chronological order 
years: [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014]
nav: true
nav_order: 2
---
<!-- _pages/publications.md -->
<div class="publications">

{%- for y in page.years %}
  {%- capture year_bib %}{% bibliography -f papers -q @*[year={{y}}]* %}{% endcapture -%}
  {%- if year_bib contains '<li' %}
  <h2 class="year">{{y}}</h2>
  {{ year_bib }}
  {%- endif %}
{% endfor %}

</div>
