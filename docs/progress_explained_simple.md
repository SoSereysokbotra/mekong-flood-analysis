# Mekong Flood Intelligence: Progress Explained in Simple Terms
**From Step 0 to Level 2 (and what Level 3 is doing)**

*A plain-English guide to why this project exists, what we discovered so far, and how the science works.*

---

## 1. The Big Picture: Why Are We Doing This?

In Cambodia and the wider Mekong region, seasonal monsoon floods can submerge hundreds of thousands of hectares of rice fields. When disaster strikes, rescue agencies and farmers need to know: **Where is the water right now?**

### The Cloud Problem & Radar
- Normal optical satellites (like cameras in space) cannot see through clouds or storm systems.
- Instead, we use **Radar satellites** (specifically Sentinel-1). Radar beams microwave pulses down to Earth through thick clouds and rain, day or night, and measures how much signal bounces back.

### The Traditional Rule: "Dark = Water"
For decades, satellite flood mapping has relied on a very simple physical rule:
* **Still water is flat and smooth like a mirror.** When radar hits open water, the beam bounces away into space. Very little energy returns to the satellite.
* **Dry land is rough.** Soil, trees, and buildings scatter radar in all directions, so a lot of energy bounces back.
* **The simple algorithm:** Any pixel that looks **dark** is water. Any pixel that looks **bright** is dry land.

```
       Radar Satellite                   Radar Satellite
            \   ^                             \   ^
             \   \                             \   \
              \   \ (energy scatters back)      \   \ (reflects AWAY)
               v   \                             v   \
         +---------------+                 ~~~~~~~~~~~~~~~~~
         | Dry Rough Land|                 ~  Open Water   ~
         +---------------+                 ~~~~~~~~~~~~~~~~~
             BRIGHT                              DARK
```

---

## 2. The Catch: The "Double-Bounce" Phenomenon

The "Dark = Water" rule works almost perfectly for lakes, wide rivers, and bare flooded dirt. **It fails completely on mature rice fields.**

When rice is tall ($80\text{ to }120\text{ cm}$), its stalks stick out above the floodwaters:
1. The radar beam hits the flat water surface.
2. The water bounces the beam horizontally directly into the vertical rice stalk.
3. The rice stalk bounces the beam **straight back to the satellite**.

This is called a **double-bounce corner reflector** (exactly how bicycle reflectors work).

```
              Radar Satellite
                  \     ^
                   \   /
                    \ / (Bounces STRAIGHT BACK!)
                     v
           Stalk    |
             |      |
        ~~~~~|~~~~~~+~~~~~~  <- Water Surface
             |
        -------------------  <- Soil Bed
              BRIGHT!
```

### The Irony
Because of double bounce, **flooded rice fields look intensely BRIGHT on radar**, often even brighter than dry land!
Therefore, every traditional flood-detection system that searches for dark pixels **completely misses flooded rice fields**. It reports them as "dry", leaving flooded agricultural communities invisible on official disaster maps.

---

## 3. Step 0: Can We Get the Data? (Data Access)

Before writing any code, we had to prove that we could get all required satellite data for Cambodia without paying for private imagery:
* **Sentinel-1 Radar:** Found free, ready-to-use scenes on Microsoft Planetary Computer covering Cambodia before, during, and after major flood events.
* **Our Target Disaster:** The catastrophic October 2020 floods in Banteay Meanchey province, Cambodia.
* **Ancillary Data:** Found global elevation maps (Copernicus DEM), historical water maps (JRC Global Surface Water), and land-use maps (ESA WorldCover).

---

## 4. Level 0: Organizing the Benchmark Dataset

To build an AI, you need high-quality data to learn from and test on. We used **Sen1Floods11**, a famous worldwide benchmark containing 446 satellite image patches ("chips") from 11 flood disasters.

We organized this data under strict scientific rules:

### A. The No-Cheating Split
We split the data strictly by **entire disaster events**, never mixing pieces of the same scene:
* **368 chips (Training):** Disasters in India, Pakistan, Bolivia, Somalia, USA, etc. The AI learns general flood patterns here.
* **48 chips (Validation):** Disasters in Spain and Nigeria. Used only to tune settings and pick our best model.
* **30 chips (Held-out Test):** The Cambodia / Mekong disaster (August 2018). **Locked away completely.** No model is ever allowed to train on it or peek at it.

### B. Land-Cover Stratification
Flood benchmark labels normally just say `flood` or `dry`. They do not specify whether the water is in a river, a forest, or a farm.
* We overlaid ESA WorldCover maps on every pixel.
* This allowed us to measure performance on **cropland** separately from **open water**, **forests**, and **cities**.

### C. Human Labels Only
Some benchmark datasets use computer algorithms ("weak labels") to label water. But those algorithms used the flawed "Dark = Water" rule! If we trained our model on them, the model would learn the exact mistake we are trying to fix. We strictly used only **hand-drawn human labels**.

---

## 5. Level 1: Measuring the Simple Baseline

Before building complex AI, we must measure how well the traditional simple method actually does.
We built a baseline using **Otsu Thresholding**: mathematically finding the single best brightness cutoff ($-19.65\text{ dB}$) to divide dark pixels from bright pixels.

### The Results on Cambodia (Held-out Test)

| Land Category | Did the simple baseline detect it? |
| :--- | :--- |
| **Open Water** (lakes, rivers) | **99.0% detected** (Nearly perfect) |
| **Dark Flooded Cropland** (submerged bare fields) | **92.4% detected** (Very good) |
| **Bright Flooded Cropland** (double-bounce rice) | **0.0% detected** (Missed every single pixel!) |

The baseline got **zero percent** recall on bright flooded cropland by construction: it assumed everything bright was dry land.

### The August 2018 "Phenology Mystery"
When we looked at the Cambodia test scene (August 5, 2018), we noticed something surprising:
* Out of 654,764 flooded cropland pixels, **only 49,960 (7.6%) were bright**. Over 92% were dark!
* Why was almost all the flooded rice dark?
* **The answer is farming calendar dates (Crop Phenology):**
  * In Cambodia, wet-season rice is planted in June–July.
  * In **early August**, rice plants are tiny seedlings ($20\text{ to }40\text{ cm}$ high).
  * When deep floodwaters hit young seedlings, the water overtops them completely. There are no tall emergent stalks to create double-bounce! It acts like open water: specular reflection $\rightarrow$ dark.
  * In **October** (our target anchor event), rice is fully mature ($80\text{ to }120\text{ cm}$), forming dense upright stalks standing in water $\rightarrow$ intense double-bounce $\rightarrow$ bright!
  * Training events (India, Pakistan) flooded when crops were mature, providing over 317,000 bright flooded crop pixels to train on.

### The Polarization Clue (VV vs. VH)
Radar satellites send and receive signals in two orientations: Vertical-Vertical (**VV**) and Vertical-Horizontal (**VH**):
* When we tested thresholding on **VV** instead of VH, it recovered **38.7%** of the bright flooded cropland!
* This gave us our first proof: **Dual-polarization (combining VV and VH) sees things that a single channel misses.**

---

## 6. Level 2: Failure Analysis (Why Does Thresholding Fail?)

In Level 2, we performed an autopsy on every mistake the simple threshold made on the Cambodia test set.

### Finding 1: Where do the errors come from?
* **Missed Floods (False Negatives):**
  * **94.0%** of all missed floods were flooded vegetation ($50\text{k}$ cropland pixels $+ 132\text{k}$ tree/marsh pixels).
  * Only $2.6\%$ were missed due to wind roughening open water.
* **False Alarms (False Positives):**
  * **58.9%** were dry, flat cropland (wet or freshly plowed soil looks smooth and dark, tricking the threshold into calling it flood).
  * Only $5.7\%$ were terrain shadows from hills.

### Finding 2: The "Single Pixel" Trap
We tested whether a computer looking at just one pixel's brightness can separate bright flooded rice from dry land.
* **Result:** AUC = $0.51\text{ to }0.53$ (equivalent to a coin flip!).
* **What this means:** A bright flooded rice pixel has the **exact same brightness** as a dry field.
* **The Breakthrough Conclusion:** No simple formula or threshold can ever solve this by looking at one pixel at a time. The only way an AI can solve this is by looking at **Spatial Context** — recognizing field boundaries, patterns, textures, and the surrounding water landscape!

### Finding 3: The Pre-Registered "Passing Grade"
To keep ourselves honest, we wrote and froze an official **Evaluation Plan** (`evaluation_plan.md`) *before* training our AI:
1. **Bright Crop Recall ($X$):** The AI must detect at least **50%** of bright flooded vegetation (beating the $39\%$ that a simple VV threshold gets for free).
2. **Cropland Precision ($Y$):** The AI must keep cropland precision above **75%** (it cannot just guess "water" everywhere to boost recall).
3. **No Regression:** It cannot break what thresholding already does well (open water recall must stay above $95\%$).
4. **Spatial Context Proof:** The AI must beat a "pixel-only" control model by at least $10\%$, proving that spatial shape recognition is doing the work.

---

## 7. Quick Summary Table: What Each Level Did

| Level | What Was Done | Key Finding |
| :--- | :--- | :--- |
| **Step 0** | Checked data availability on Planetary Computer | All Sentinel-1, DEM, and land-cover data is freely accessible. |
| **Level 0** | Downloaded and cataloged 446 chips across 11 disasters | Split data by event (368 train, 48 valid, 30 held-out test). Stratified by land type. |
| **Level 1** | Built simple "Dark = Water" baseline (Otsu threshold) | Detected 99% open water, but 0% bright flooded rice. Proved VV recovers 39% of bright pixels. |
| **Level 2** | Analyzed all failures; checked crop calendar and pixel distributions | 94% of missed floods are flooded plants. Single pixels are inseparable (AUC ~0.50); AI **must** use spatial context. Pre-registered the evaluation criteria. |
| **Level 3** *(Now)* | Training computer-vision AI (U-Net) on dual-pol radar + terrain | Testing if 2D spatial context can reliably detect flooded crops without false alarms. |

---

## 8. What Level 3 Is Doing Right Now

Level 3 takes everything learned above into machine learning:
1. **Architecture:** A **U-Net** neural network. Instead of classifying one pixel, it looks at entire $256 \times 256$ patches of land to see shapes, edges, and textures.
2. **Inputs:** Dual-pol radar ($VV + VH$) plus elevation slope (to avoid hill shadows).
3. **Training:** Trains on the diverse worldwide flood events (India, Pakistan, Somalia) where mature crops double-bounced, validates on Spain and Nigeria, and will be graded against our frozen Cambodia test rules.
