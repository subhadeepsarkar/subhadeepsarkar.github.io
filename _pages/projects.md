---
layout: page
title: Research
permalink: /projects/
# description: Current projects.
nav: true
nav_order: 1
---


My research interests include storage engines, access methods, and data management systems. I am also interested in understanding the performance vs. privacy tradeoffs in modern data systems and building end-to-end privacy compliant data systems. Here is my <a href="/assets/resources/research_statement.pdf" target="_blank">latest research statement</a>. <br><br><br>

<div class="projects">
  <!-- Display categorized projects -->
  <h2 class="category" style="margin-top: -40px;">current projects</h2>
  <div style="width: 20%; float:left; margin-top: 20px; margin-bottom: 90px;">
    <figure>
      <picture>
        <source class="responsive-img-srcset" media="(max-width: 480px)" srcset="/al-folio/assets/img/1-480.webp">
        <!-- Fallback to the original file -->
        <img src="/assets/img/p1.jpg" class="img-fluid z-depth-1" width="auto" height="auto" title="example image" onerror="this.onerror=null; $('.responsive-img-srcset').remove();">
      </picture>
    </figure>
  </div>
  <div style="width: 78%; float:right; margin-top: 2px; margin-bottom: 75px;">
      <span style="font-size: 30px;">Deletion-Compliant Data Systems</span>
      <br> 
      <span style="font-size: 15px;">Modern data are curated to support fast ingestion and fast query processing, and they do so ny handling the incoming data in an out-of-place fashion. Deletes in such data stores are realized logically by inserting additional metadata. This has severe implications on the privacy front, especially, in light of the newly enforced privacy regulations. The GDPR's right to be forgotten, right to delete in California's CCPA and CPRA, and deletion right in Virginia's VCDPA are all aimed toward the common goal of enabling the end-users to express their preferences about the deletion of their personal data. As out-of-place systems are built with the underlying assumption of perpetual data retention, by design, they are unable to persistently delete the user data in a time-bound manner. The objective of my research is to design data stores that offer optimal performance while ensuring timely and persistently deleting data from modern out-of-place data stores. </span>
  </div>

  <div class="projects" style="width: 20%; float:left; margin-top: 8px; margin-bottom: 125px;">
    <figure>
      <picture>
        <source class="responsive-img-srcset" media="(max-width: 480px)" srcset="/al-folio/assets/img/1-480.webp">
        <!-- Fallback to the original file -->
        <img src="/assets/img/p2.jpg" class="img-fluid z-depth-1" width="auto" height="auto" title="example image" onerror="this.onerror=null; $('.responsive-img-srcset').remove();">
      </picture>
    </figure>
  </div>
  <div style="width: 78%; float:right; margin-top: -20px; margin-bottom: 75px;">
      <span style="font-size: 30px;">Modern Storage Systems and Data Structures</span>
      <br> 
      <span style="font-size: 15px;">Performance of data systems are dictated by the data structures and access methods used at the heart of the storage engine. Log-structure merge-trees (LSM-trees) are one of the most commonly used data structures in modern key-value stores, including RocksDB at Meta and Rockset, LevelDB and BigTable at Google, Cassandra and HBase at Apache, and so on. While LSM-tree-based storages are designed to support update-heavy workloads, in the era of hybrid transactional/analytical processing (HTAP), workloads are combination of read and update queries. This requires optimization and tuning of the LSM-tree design space, careful re-allocation and utilization of the resources, and robust organization of the data. In this light, my research focuses on re-visiting the LSM-tree design space to optimize the resource (memory, I/O etc.) utilization -- particularly for the less visited operations, such as persistent and timely deletion of data. </span>
  </div>
</div>




<div class="projects">
  <!-- Display categorized projects -->
  <h2 class="category" style="margin-top: 0px; width: 100%;">past projects</h2>
  <div style="width: 20%; float:left; margin-top: 20px; margin-bottom: 75px;">
    <figure>
      <picture>
        <source class="responsive-img-srcset" media="(max-width: 480px)" srcset="/al-folio/assets/img/1-480.webp">
        <!-- Fallback to the original file -->
        <img src="/assets/img/p3.jpg" class="img-fluid z-depth-1" width="auto" height="auto" title="example image" onerror="this.onerror=null; $('.responsive-img-srcset').remove();">
      </picture>
    </figure>
  </div>
  <div style="width: 78%; float:right; margin-top: 2px; margin-bottom: 75px;">
      <span style="font-size: 30px;">Fog Computing</span>
      <br> 
      <span style="font-size: 15px;">I also have an active interest in FOG (From cOre to edGe) computing-based research. Rather than opposing the principles of classical cloud computing, fog offers a complementary set of features, which are truly unique. Thus, together with cloud, fog computing offers a new breed of computing paradigm which would directly benefit the IoT by providing an appropriate service infrastructure for the cause. It is interesting, at this relatively early stage, to analyze the several challenges of fog computing, and analyze the performance of fog in contrast with the classical cloud computing model. My research articles on fog computing (see here and here) have been very well received by the community. Fog and cloud-based systems are also the primary application domains for my current research on data and storage systems. I have also co-authored a book on fog computing. </span>
  </div>
  <br><br>

