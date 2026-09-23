# Radar Preprocessing: Explained in Simple Terms
**From Raw Satellite Pulses to Flood Intelligence**

*A plain-English guide to how raw radar signals are cleaned, calibrated, corrected, and why a tiny pre-processing mismatch almost broke our models.*

---

## 1. Why Does Raw Radar Need Preprocessing?

When the Sentinel-1 satellite flies over Cambodia, it does not record a ready-to-view JPEG photo. 

It records raw digital echoes: timing delays and microwave frequencies stored as complex numbers. If you tried to display a raw Sentinel-1 file immediately, it would look like a distorted, upside-down, blurry funhouse mirror!

To turn those raw echoes into an accurate map on Earth, every radar image must pass through a 4-step assembly line called the **SAR Preprocessing Pipeline**:

```
+---------------------------------------------------------------------------------+
|                       THE 4-STEP RADAR PREPROCESSING PIPELINE                   |
+-------------------+--------------------+-------------------+--------------------+
| 1. ORBIT          | 2. RADIOMETRIC     | 3. TERRAIN        | 4. DECIBEL (dB)    |
|    CORRECTION     |    CALIBRATION     |    CORRECTION     |    CONVERSION      |
| "Where was the    | "Convert raw digit | "Fix mountain     | "Convert power to  |
| satellite down to | numbers into real  | distortion using  | an intuitive human |
| the centimeter?"  | physical power"    | a 3D elevation map" scale"              |
+-------------------+--------------------+-------------------+--------------------+
```

---

## 2. Step-by-Step: The Preprocessing Assembly Line

### Step 1: Orbit Correction (Pinpoint Accuracy)
* **The Problem:** The satellite orbits Earth at 27,000 km/h (7.5 km per second). While transmitting, its GPS location is slightly estimated. A tiny error in the satellite's position puts the resulting flood map hundreds of meters away from where it actually is on the ground!
* **The Fix:** A few days after a satellite pass, space agencies (ESA) publish **Precise Orbit Ephemerides (POEORB)**. This file records the satellite's exact position in space down to **less than 5 centimeters**.
* **What this step does:** It updates the radar image metadata with the satellite's exact orbit, ensuring that a flooded road in Sisophon aligns perfectly with the actual road on OpenStreetMap.

---

### Step 2: Radiometric Calibration (Digital Numbers -> Real Physical Power)
* **The Problem:** The raw satellite image contains arbitrary numbers called **Digital Numbers (DN)** (e.g., integer values from 0 to 65,535). These numbers depend on how hot the satellite antenna was, its distance to Earth, and electronic sensor gain.
* **The Fix:** We apply calibration mathematical tables provided by the satellite engineers.
* **What this step does:** It converts those arbitrary sensor integers into a true physical measurement of radar reflectivity called **Radar Cross Section (Power)**. Now, -18 dB means the exact same physical roughness whether measured in 2018 or 2026.

---

### Step 3: Geometric Terrain Correction (Fixing the Funhouse Mirror)
This is the most mathematically complex step in radar processing.

Because radar looks sideways at the Earth (at an angle of about 30 to 45 degrees), tall mountains and hills suffer from severe optical distortions:

```
            Satellite Radar Pulse
               \
                \     Mountain Peak (Closer to satellite!)
                 \       ^
                  \     / \
                   v   /   \
           ------------     \-----------------
               Valley        Behind the ridge
```

* **Foreshortening & Layover:** Because the mountain peak is physically closer to the satellite than the valley floor below it, the radar echo from the mountain peak bounces back **first**! The satellite thinks the mountain peak is in front of the valley, making mountains appear squashed, tilted, or folded over like an accordion!
* **Radar Shadow:** The back side of the steep mountain is completely blocked from the radar beam, creating a pitch-black zone with zero signal (which simple algorithms mistake for water!).
* **The Fix (Range-Doppler Orthorectification):** We take a 3D elevation map (such as the Copernicus 30-meter DEM) and use trigonometry to move every single pixel to its true geographic latitude, longitude, and elevation on Earth.

---

### Step 4: Decibel (dB) Conversion (Linear Power -> Logarithmic Decibels)
* **The Problem:** Calibrated linear power is full of awkward, tiny decimal fractions (like `0.0000842` for water or `0.0821` for buildings).
* **The Fix:** We convert linear power into decibels using the formula:
  `dB = 10 * log10(Power)`
* **What this produces:**
  * Clean, manageable negative numbers:
    * **-30 dB to -24 dB:** Water
    * **-18 dB to -14 dB:** Farmland / Grass
    * **-10 dB to -5 dB:** Flooded Rice / Cities

---

## 3. Sigma-Nought vs. Gamma-Nought (And Why Mixing Them Almost Broke Our Project)

This was the single most dangerous scientific trap in our project, and finding it is what saved Level 3!

Both **Sigma-nought** and **Gamma-nought** measure radar backscatter, but they calculate area on the ground differently:

```
A. SIGMA-NOUGHT (Flat Earth Area)           B. GAMMA-NOUGHT / RTC (True 3D Surface Area)

              Satellite                                  Satellite
                  \                                          \
                   \                                          \
                    v                                          v
               +---------+                                   / \  Sloped Mountain
               | Flat    |                                  /   \ Surface Area
               | Ground  |                                 /     \ (Calculated using 3D DEM)
               +---------+                                +-------+
```

### What is Sigma-nought?
* Calculates how much radar bounces back per square meter of ground, **assuming the Earth is a flat, smooth ellipsoid**.
* Simple to compute, but on hills and slopes, the brightness is distorted because it ignores the true terrain tilt.
* **This is what the raw Sen1Floods11 benchmark dataset used.**

### What is Gamma-nought (RTC)?
* **RTC stands for Radiometric Terrain Correction.**
* It uses a 3D digital elevation model (Copernicus DEM) to calculate the **true 3D surface area perpendicular to the radar beam**.
* It removes the brightening on hill slopes facing the satellite and normalizes brightness across flat valleys and ridges alike.
* **This is what modern operational pipelines (Microsoft Planetary Computer Sentinel-1 RTC) use for Cambodia.**

---

### Why Mixing Them Breaks a Machine Learning Model:

In Level 4 pre-flight testing, we took our winning U-Net model (which was trained on the Sen1Floods11 benchmark using Sigma-nought) and tested it on the exact same Cambodia chips processed with Planetary Computer Gamma-nought (RTC).

**The Result was a Total Disaster:**
* The model's score collapsed from **0.820 IoU down to 0.138 IoU**! It was failing completely.

#### Why did it fail?
Because **Gamma-nought is systematically about 1.8 dB brighter than Sigma-nought** across the entire landscape!

```
    Model trained on Sigma-nought:
    Water threshold learned by AI:  -19.65 dB
    Actual Gamma-nought Water:      -17.85 dB  (Shifted 1.8 dB brighter!)
```

Because the entire image was 1.8 dB brighter, the AI thought the water was "too bright to be water" and called real floods dry land!

#### The Lesson (Rule 9 of our Project Plan):
A neural network does not know physics; it only knows the numbers you feed it. If you train on Sigma-nought and deploy on Gamma-nought, the model fails because of a **data formatting shift**, not because the AI is bad!

To solve this, we upgraded to **Level 3 v1.1**: we re-processed the training data through the Planetary Computer RTC pipeline, re-trained the U-Net on Gamma-nought, and the model instantly recovered to **0.827 precision and 0.790 bright rice recall**!

---

## 4. Speckle Filters: Cleaning the Grain (And Their Trade-offs)

In the previous guide, we learned that **Speckle** is the salt-and-pepper grain in radar images caused by physical wave interference between grass blades and dirt clods.

To clean this grain, engineers use **Speckle Filters**. The two most famous are the **Lee Filter** and the **Refined Lee Filter**.

---

### A. The Classic Lee Filter
* **How it works:** It slides a small window (e.g., 5 x 5 pixels) across the image.
  * In flat, smooth areas (low variance): it acts like an **averaging blur**, smoothing out the noisy dots.
  * Near sharp edges (high variance): it turns off the blur to preserve the edge.
* **The Analogy:** Think of an automatic beauty filter on a phone that smooths your skin while trying not to blur your eyelashes.

---

### B. The Refined Lee Filter
* **The Problem with the Classic Lee Filter:** When a 5 x 5 window touches a sharp diagonal boundary (like a straight canal cut through farmland), it gets confused and blurs the corners.
* **The Refined Lee Solution:** Instead of using the whole square, it splits the 5 x 5 window into **8 directional edge masks** (horizontal, vertical, diagonal, etc.).
* It finds the direction of the boundary, averages pixels only on *one side* of the edge, and leaves the boundary razor-sharp!

```
                  THE 8-DIRECTIONAL MASKS OF REFINED LEE
                  
          [ X X X ]        [ . . X ]        [ . . . ]
          [ . . . ]        [ . X . ]        [ . . . ]
          [ . . . ]        [ X . . ]        [ X X X ]
         Horizontal        Diagonal        Opposite Edge
```

---

### C. The Critical Trade-offs for Cambodian Rice Farming

If speckle filters smooth out noise, why didn't we just filter all our training data?

Because Asian rice farming has unique physical dimensions:

| Farm Feature | Real-world Size on Ground | Size on Satellite Image (10m resolution) | What happens if you apply a 7x7 Speckle Filter? |
| :--- | :--- | :--- | :--- |
| **Small Rice Paddy** | 20 meters x 30 meters | 2 x 3 pixels | Completely blurred and blended with neighboring dry fields! |
| **Earthen Field Bund (Dike)** | 1 meter to 2 meters | Sub-pixel (0.1 to 0.2 pixels) | Erased completely! |
| **Irrigation Ditch** | 2 meters to 3 meters | Sub-pixel | Washed out into background soil! |

### The Verdict on Filtering:
1. **Traditional Math / Thresholding:** Needs speckle filtering because a single noisy bright pixel inside a dark lake will fool a simple threshold.
2. **Deep Learning (Our U-Net):** **Performs best on unfiltered data!** A convolutional neural network has its own learned convolutional filters. It naturally learns to ignore salt-and-pepper speckle while preserving the crisp, narrow shapes of 10-meter rice field boundaries.

---

## Summary Reference Table

| Preprocessing Step | Plain-English Purpose | What happens if you skip it? |
| :--- | :--- | :--- |
| **Orbit Correction** | Uses post-flight ephemeris (POEORB) to pinpoint satellite position to < 5 cm. | Your flood map is misaligned by hundreds of meters. |
| **Radiometric Calibration** | Converts raw sensor integers into true physical power reflectivity. | Cannot compare images taken on different dates or years. |
| **Terrain Correction (RTC)** | Uses a 3D elevation map (DEM) to undo mountain tilt and foreshortening. | Mountains appear squashed over valleys, and hill slopes look artificially bright. |
| **Decibel (dB) Conversion** | Converts fractional power to logarithmic scale (0 to -30 dB). | Neural networks and human analysts struggle with tiny decimal fractions. |
| **Sigma vs. Gamma** | Sigma assumes flat Earth; Gamma (RTC) normalizes for true 3D surface slope. | Mixing them causes a ~1.8 dB brightness shift that breaks trained models. |
| **Speckle Filtering** | Smooths out salt-and-pepper wave interference grain. | Reduces noise, but blurs narrow field bunds and small 20m rice paddies. |
