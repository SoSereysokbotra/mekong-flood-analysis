# Radar Physics & Flood Detection: Explained in Simple Terms
**The Essential Guide to Radar, Polarisation, Double Bounce, and Speckle**

*This guide breaks down the core physics behind this project into plain English, using everyday analogies and visual diagrams.*

---

## 1. Radar Fundamentals: The Microwave Flashlight

To understand satellite flood mapping, you first need to understand the difference between taking a regular photograph and using radar.

### Optical Satellites (Cameras in Space)
* Traditional satellites (like Sentinel-2 or Google Earth) are **passive**. They work just like your smartphone camera: they rely on sunlight reflecting off the Earth.
* **The Problem:** When monsoon floods hit Cambodia, the sky is covered by thick storm clouds and rain. An optical camera cannot see through clouds; it only takes pictures of the white cloud tops. At night, it sees nothing.

### Radar Satellites (Sentinel-1)
* Radar satellites are **active**. The satellite carries its own powerful microwave transmitter and antenna.
* Think of it as a satellite orbiting in space with a **giant microwave flashlight**:
  1. It shoots high-speed pulses of microwave energy down to Earth.
  2. The energy hits the ground, buildings, trees, and water.
  3. The satellite's antenna listens for the echo bouncing back.
  4. It works identically **day or night**.

```
    Optical (Passive Camera)                  Radar (Active Flashlight)
          Sun                                         Satellite
           \                                           /     ^
            \ (Sunlight blocked by clouds!)      Pulse/       \ Echo
             v                                       /         \
         ~~~~~~~~ (Thick Monsoon Clouds)          ~~~~~~~~      ~~~~~~~~
                                                 (Radar beams pass right through!)
                                                     v           ^
         ===============================          ===============================
                  Earth's Surface                          Earth's Surface
```

### Why can Radar see through clouds and rain?
It all comes down to **wavelength**:
* Visible light has a tiny wavelength ($\approx 0.0005\text{ mm}$). Cloud droplets ($0.01\text{ to }0.05\text{ mm}$) are much larger than light waves, so light scatters in all directions (like fog blinding your car headlights).
* Sentinel-1 radar uses **C-band microwaves** with a wavelength of **$\approx 5.6\text{ cm}$** ($2.2\text{ inches}$). 
* Because a $5.6\text{ cm}$ microwave wave is thousands of times larger than cloud droplets, it passes straight through storm clouds and rain as if they weren't even there!

---

## 2. What is "Backscatter"? (The Echo Strength)

When the radar pulse hits the ground, it bounces in various directions. **Backscatter** is the portion of that energy that reflects **directly back to the satellite's antenna**.

### The Sound Echo Analogy
* **High Backscatter:** Imagine standing in front of a flat, hard concrete canyon wall and shouting. The sound bounces straight back to your ears loud and clear.
* **Low Backscatter:** Imagine standing in the middle of a vast, open, grassy soccer field and shouting. Your voice travels forward into the horizon; almost nothing bounces back to you.

```
                      Satellite Antenna
                          \       ^
                           \     /
              Sent Pulse    \   /  BACKSCATTER (Energy returning to sensor)
                             v /
                        [ Target ]
```

### Why do we measure Backscatter in Decibels (dB)?
The raw energy returning to the satellite is tiny. For water, only $0.0001$ ($0.01\%$) of the energy returns. For a steel bridge or city building, $0.1$ ($10\%$) might return. 

Because comparing $0.0001$ to $0.1$ is awkward, radar scientists convert raw power into a logarithmic scale called **Decibels (dB)**:
$$\text{dB} = 10 \cdot \log_{10}(\text{Power})$$

### The Radar Brightness Cheat-Sheet in our Project:
* **$-30\text{ dB}$ to $-24\text{ dB}$ (Very Dark / Low Echo):** Calm lakes, open rivers, smooth paved runways.
* **$-18\text{ dB}$ to $-14\text{ dB}$ (Medium Gray / Normal Echo):** Dry cropland, grassland, bare dirt.
* **$-10\text{ dB}$ to $-5\text{ dB}$ (Very Bright / Huge Echo):** Flooded mature rice fields, metal bridges, tall skyscrapers.

*(Every $+10\text{ dB}$ increase means the returning echo is $10\times$ stronger!)*

---

## 3. Why Does Calm Water Appear Dark? (The Mirror Effect)

The traditional rule of satellite flood mapping is: **"Dark pixels = Water."** 

Here is the physics of why that rule normally works:

```
A. CALM OPEN WATER (Specular Reflection)     B. ROUGH DRY LAND (Diffuse Scattering)

             Satellite                                   Satellite
                \                                           \       ^
                 \                                           \     /
                  \                                           \   / (Energy scatters in
                   \ (Bounces AWAY into space)                 v /   all directions;
                    v                                      /\/\/\/\   some returns!)
             ~~~~~~~~~~~~~~~                              ----------------
               Smooth Water                                  Rough Soil
             ALMOST ZERO ECHO                               STRONG ECHO
           -> LOOKS JET BLACK                             -> LOOKS MEDIUM GRAY
```

1. **Specular Reflection (Mirror):**
   * Calm water is completely flat and smooth compared to a $5.6\text{ cm}$ radar wave.
   * When the radar beam strikes calm water at an angle ($\sim 35^\circ$), it reflects cleanly forward away from the satellite, like a laser beam hitting a bathroom mirror.
   * Because the energy bounces away into space, almost no echo returns to the satellite antenna.
   * On the radar image, the water looks **jet black ($-28\text{ dB}$)**.

2. **The Exception (Wind Roughening):**
   * If a strong wind blows across a lake, it kicks up small waves and ripples ($2\text{ to }6\text{ cm}$).
   * These ripples act like thousands of tiny tilted mirrors facing the satellite, reflecting energy back.
   * Wind-blown water can look gray instead of black, tricking simple algorithms into thinking it is dry land!

---

## 4. VV vs. VH Polarisation: The Wave's Vibration Direction

Radar waves are electromagnetic waves. Just like a vibrating guitar string, the wave can oscillate in different physical directions.

* **Vertical Polarization (V):** The wave vibrates up-and-down.
* **Horizontal Polarization (H):** The wave vibrates side-to-side.

```
       Vertical Wave (V)                         Horizontal Wave (H)
              |   ^                                     <-------->
              |   |                               (Vibrates horizontally,
              v   |                                    left-to-right)
     (Vibrates vertically,
          up-and-down)
```

Sentinel-1 is a **dual-polarized** satellite. It sends out a **Vertical (V)** wave, and its antenna listens for **two separate echoes simultaneously**:

| Polarization | What It Means | Physical Behavior | What It Sees Best |
| :--- | :--- | :--- | :--- |
| **VV** (Co-pol) | Sent **V**ertical, Received **V**ertical | The wave bounces back with its orientation unchanged. | Sensitive to flat water mirrors and vertical stalks. |
| **VH** (Cross-pol) | Sent **V**ertical, Received **H**orizontal | The wave was sent vertical, but came back horizontal! (Depolarization). | Sensitive to complex 3D plant canopies and forests. |

### How does a wave twist from V to H?
A vertical wave **cannot twist into a horizontal wave** when bouncing off a flat water surface or flat dirt. 

It can **only twist** if it penetrates inside a complex 3D volume (like leafy tree branches, bushes, or dense crop canopies) and bounces multiple times between leaves and stems. This is called **Volume Scattering**.

### Why Dual-Pol is Crucial for Floods:
* In **VH**, calm water has zero volume scattering $\rightarrow$ water is pitch black ($-32\text{ dB}$).
* In **VV**, the vertical waves interact strongly with standing vertical plant stems.
* In Level 1, we discovered that **VV recovered 39% of bright flooded rice** that VH missed, because VV captured the vertical rice geometry!

---

## 5. Double Bounce: Why it Inverts the Signal!

This is the central mystery this entire project is built to solve.

Under the traditional rule, flooding a field should make it **darker** (dry dirt $\approx -16\text{ dB} \rightarrow$ submerged water $\approx -28\text{ dB}$). 

**Double bounce does the exact opposite: it turns a field into a blazing bright spotlight!**

### The Bicycle Reflector Analogy
A plastic bicycle reflector has no batteries or bulbs. Yet, when car headlights shine on it at night, it glows blindingly bright back at the driver. 
* *Why?* Inside the reflector are tiny plastic cubes with two walls meeting at a **$90^\circ$ right angle** (a **corner reflector**). 
* Light hits wall 1, bounces to wall 2, and bounces **straight back to the car**!

```
                    THE BICYCLE REFLECTOR PRINCIPLE
                    
                          Incoming Beam
                                \        ^  Returning Echo
                                 \      /  (Straight back!)
                                  \    /
                           Wall 1  \  / 
                           |        v/
                           |        /|
                           |       / |
                           +---------+  Wall 2 (90° corner)
```

### How Double Bounce Happens in a Rice Field:
When rice is mature ($80\text{ to }120\text{ cm}$ tall), its stiff, vertical stalks stick out above the floodwater:

```
                            Satellite
                                \        ^
                                 \      /
                    Radar Pulse   \    /  Echo bounces STRAIGHT BACK!
                                   \  /
                             Stalk  \/
                               |    /|
                               |   / |
                          ~~~~~|~~/~~+~~~~~  <- Flat Water Mirror
                               |
                          -----------------  <- Soil Bed
```

1. The radar pulse strikes the flat, smooth floodwater.
2. The water acts as a horizontal mirror, reflecting the pulse forward directly into the vertical rice stalk.
3. The vertical rice stalk acts as a vertical mirror at a $90^\circ$ angle, bouncing the beam **directly back to the satellite**!

### Why this "Inverts" the Signal:
* **Dry Paddy Field:** Stalks grow out of rough soil. Radar bounces off the rough ground in all random directions $\rightarrow$ moderate return (**$-16\text{ dB}$**, medium gray).
* **Flooded Paddy Field:** The rough soil is replaced by a flat water mirror. Together with the stalks, they form thousands of perfect corner reflectors $\rightarrow$ massive return (**$-10\text{ dB}$**, intense white)!

```
    Normal Expectation:  Flooding makes things DARKER  ( -16 dB -> -28 dB )
    Double Bounce Reality: Flooding makes rice BRIGHTER ( -16 dB -> -10 dB )
```

**The Fatal Mistake:** Because traditional computer algorithms search for dark pixels, they look at this bright flooded field and say: *"This pixel is bright, so it must be dry land!"* They miss the flooded rice completely.

---

## 6. Speckle and Filtering: The Salt-and-Pepper Grain

If you zoom into any raw Sentinel-1 radar image, it looks grainy, like someone sprinkled black and white salt and pepper all over the picture:

```
             RAW RADAR IMAGE (Speckle Noise)
             
             [ -12dB ]  [ -28dB ]  [ -10dB ]
             [ -24dB ]  [ -14dB ]  [ -18dB ]
             [ -11dB ]  [ -26dB ]  [ -13dB ]
```

### Where does Speckle come from?
Speckle is **not camera noise or a broken sensor**. It is physical **wave interference**:
* A single pixel on the ground is $10\text{ meters} \times 10\text{ meters}$ ($100\text{ m}^2$).
* Inside that one pixel, there are millions of tiny individual things: grass blades, dirt clods, pebbles.
* When the radar wave hits that pixel, individual waves bounce off each pebble and travel back:
  * If two wave peaks collide (**Constructive Interference**), they boost each other $\rightarrow$ **bright white pixel**.
  * If a wave peak meets a wave trough (**Destructive Interference**), they cancel each other out $\rightarrow$ **pitch black pixel**.
* Even if a field is completely flat and uniform, wave interference causes it to look like salt-and-pepper grain.

### Speckle Filtering (Averaging)
To remove the grain, traditional software uses a **Speckle Filter** (like a Lee filter or Boxcar filter), which replaces each pixel with the average of its neighbors.

### The Big Trap (Why we avoided heavy filtering):
* Averaging smooths out the salt-and-pepper dots, **but it blurs sharp edges**.
* In Asian rice farming, fields are small ($20\text{ m} \times 30\text{ m}$), separated by narrow $1\text{-meter}$ earthen dikes (bunds) and small irrigation ditches.
* If you apply heavy speckle filtering, you blur the boundaries and completely wash away the narrow rice paddies!
* **Why our Level 3 U-Net was superior:** Rather than dumb spatial blurring, a convolutional neural network (U-Net) learns to recognize real field textures and landscape patterns while keeping the boundaries sharp.

---

## Summary Reference Table

| Physical Concept | What It Is | How It Affects Flood Mapping |
| :--- | :--- | :--- |
| **Radar (SAR)** | Active microwave satellite ($5.6\text{ cm}$ wavelength). | Pierces through storm clouds and rain to map monsoon floods. |
| **Backscatter** | The echo strength bouncing back to the satellite (in dB). | Water is usually low ($-28\text{ dB}$); dry land is medium ($-16\text{ dB}$). |
| **Specular Reflection** | Mirror-like bounce away from flat surfaces. | Why calm open water looks jet black on radar. |
| **VV vs. VH** | Vertical vs. Cross-polarized wave orientations. | VH shows tree canopies; VV is sensitive to vertical rice stalks and recovers 39% of bright floods. |
| **Double Bounce** | Water + stalk forming a $90^\circ$ bicycle reflector. | **Inverts the signal:** makes flooded mature rice look **bright ($-10\text{ dB}$)** instead of dark, causing simple detectors to miss it. |
| **Speckle** | Salt-and-pepper grain caused by wave interference. | Why single-pixel rules fail, requiring 2D spatial AI (U-Net) to see shapes and context. |
