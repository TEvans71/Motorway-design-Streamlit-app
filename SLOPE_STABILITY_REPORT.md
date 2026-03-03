# Slope Stability Analysis — Detailed Technical Report

## 1. Overview

The motorway design application implements **short-term undrained** slope stability analysis for embankments on soft clay. Two methods are available in the codebase:

1. **φ = 0 Ordinary Method of Slices** — Primary method used in the UI (lecture-style)
2. **Short-term Undrained Moment Method** — Alternative method (used in grid search)

Both assume **φ = 0** (undrained conditions) and use **circular slip surfaces**.

---

## 2. Method 1: φ = 0 Ordinary Method of Slices

### 2.1 Theoretical Basis

For undrained clay (φ = 0), shear strength is:

$$\tau = c_u$$

The factor of safety is defined as the ratio of **resisting force** to **driving force** along the slip surface:

$$F = \frac{\sum T_i}{\sum D_i}$$

where:
- \( T_i \) = resisting force on slice \( i \) (mobilised shear resistance)
- \( D_i \) = driving force on slice \( i \) (downslope component of weight)

### 2.2 Formulas

**Resisting force per slice:**

$$T_i = c_u \cdot b \cdot \sec\alpha$$

**Driving force per slice:**

$$D_i = W_i \cdot \sin|\alpha|$$

**Factor of safety:**

$$F = \frac{\sum_{i=1}^{n} (c_u \cdot b \cdot \sec\alpha_i)}{\sum_{i=1}^{n} (W_i \cdot \sin|\alpha_i|)}$$

### 2.3 Symbols and Definitions

| Symbol | Description | Unit |
|--------|-------------|------|
| \( c_u \) | Undrained shear strength | kPa |
| \( b \) | Slice width (horizontal) | m |
| \( \alpha \) | Angle of slip surface tangent at slice midpoint (from horizontal) | rad |
| \( W_i \) | Weight of slice \( i \) | kN/m (per metre run) |
| \( \sec\alpha \) | \( 1/\cos\alpha \) — converts horizontal base length to arc length | — |
| \( n \) | Number of slices | — |

### 2.4 Angle α (Slope of Slip Surface)

The angle \( \alpha \) is derived from the geometry of the circular slip surface. At each slice midpoint \( (x_{mid}, z_{base}) \):

$$\frac{dz}{dx} = -\frac{x_{mid} - x_c}{z_{base} - z_c}$$

$$\alpha = \arctan\left(\frac{dz}{dx}\right)$$

where:
- \( x_c, z_c \) = centre of slip circle
- \( z_{base} \) = elevation of slip arc at slice midpoint

### 2.5 Slice Weight \( W_i \)

Each slice is subdivided into **fill** (above ground) and **clay** (below ground):

$$A_{fill} = \max(0, z_{surf} - \max(z_{base}, z_{ground})) \times b$$

$$A_{clay} = \max(0, \min(z_{surf}, z_{ground}) - z_{base}) \times b$$

$$W_i = \gamma_{fill} \cdot A_{fill} + \gamma_{clay} \cdot A_{clay}$$

### 2.6 Slip Arc Geometry

The lower arc of the circle (soil side) is:

$$z_{base}(x) = z_c - \sqrt{R^2 - (x - x_c)^2}$$

The slip surface intersects the ground surface at two points \( x_L \) and \( x_R \), found by solving:

$$z_{surface}(x) - z_{base}(x) = 0$$

using a sign-change scan over \( x \in [x_c - R, x_c + R] \).

### 2.7 Input Parameters (φ = 0 Method)

| Parameter | Symbol | Description | Typical source |
|-----------|--------|-------------|----------------|
| Undrained shear strength | \( c_u \) | cu_kpa | Geotechnical input |
| Fill unit weight | \( \gamma_{fill} \) | gamma_fill | kN/m³ |
| Clay unit weight | \( \gamma_{clay} \) | gamma_clay | kN/m³ |
| Number of slices | \( n \) | n_slices | User input (e.g. 20) |
| Ground level | \( z_{ground} \) | ground level | From cross-section at x_stability |
| Finished level | \( Z_{finish} \) | Z_finish | From profile |
| Top width | \( B_{top} \) | B_top | Geometry |
| Base width | \( B_{base} \) | B_base | From H_fill and side slope |

### 2.8 Trial Circle Centres

Six trial circles are evaluated with different centre positions:

| Trial | Slope position | Crest height | Toe offset |
|-------|-----------------|--------------|------------|
| 1 | Left | 0H above crest | 2H from toe |
| 2 | Middle | 0H above crest | 2H from toe |
| 3 | Right | 0H above crest | 2H from toe |
| 4 | Left | 3/4H above crest | 4H from toe |
| 5 | Middle | 3/4H above crest | 4H from toe |
| 6 | Right | 3/4H above crest | 4H from toe |

**Centre resolution (descriptor mode):**

$$x_{base} = x_{toe} + \text{sign} \times \text{toe\_offset\_factor} \times H$$

$$x_c = x_{base} + \text{lateral\_shift}$$

$$z_c = z_{crest} + \text{crest\_height\_factor} \times H$$

- **Lateral shift:** Left = \(-0.5 \times \text{slope\_span}\), Middle = 0, Right = \(+0.5 \times \text{slope\_span}\)
- **Radius:** \( R = \sqrt{(x_c - x_{toe})^2 + (z_c - z_{toe})^2} \)

**Constraint:** \( R \leq 4H \) (radius must not exceed 4× embankment height).

---

## 3. Method 2: Short-term Undrained Moment Method

### 3.1 Theoretical Basis

For a circular slip surface, equilibrium is expressed in terms of **moments** about the circle centre:

- **Driving moment** \( M_{drive} \): due to weight of sliding mass
- **Resisting moment** \( M_{resist} \): due to shear resistance along the arc

$$F = \frac{M_{resist}}{M_{drive}}$$

### 3.2 Formulas

**Resisting moment:**

$$M_{resist} = c_u \cdot L_{arc} \cdot R$$

where:
- \( L_{arc} \) = length of slip arc (m)
- \( R \) = radius of slip circle (m)

**Driving moment (per slice):**

$$M_{drive,i} = W_i \cdot d_i$$

$$d_i = |y_{mid} - y_c|$$

**Total driving moment:**

$$M_{drive} = \sum_{i} W_i \cdot d_i$$

**Factor of safety:**

$$F = \frac{c_u \cdot L_{arc} \cdot R}{\sum_i W_i \cdot d_i}$$

### 3.3 Slice Geometry (Moment Method)

- **Slice width:** \( \Delta y = (y_{max} - y_{min}) / n \)
- **Slice area:** \( A_i = h_i \times \Delta y \), where \( h_i = \max(0, z_{surf} - z_{slip}) \)
- **Weight:** \( W_i = \gamma \cdot A_i \)

**Unit weight selection** (unit_weight_option):

| Option | Rule |
|--------|------|
| gamma_fill | Use \( \gamma_{fill} \) for all slices |
| gamma_clay | Use \( \gamma_{clay} \) for all slices |
| gamma_fill_above_ground + gamma_clay_below | \( \gamma_{fill} \) if \( z_{centroid} \geq z_{ground} \), else \( \gamma_{clay} \) |

### 3.4 Arc Length Formula

For chord from \( y_1 \) to \( y_2 \):

$$\text{chord} = |y_2 - y_1|$$

$$\theta = 2 \arcsin\left(\min\left(1, \frac{\text{chord}}{2R}\right)\right)$$

$$L_{arc} = R \cdot \theta$$

### 3.5 Circle–Ground Intersection

The slip circle \( (y_c, z_c, R) \) intersects the horizontal ground line \( z = z_{ground} \) when:

$$\Delta = R^2 - (z_{ground} - z_c)^2 > 0$$

$$y_1 = y_c - \sqrt{\Delta}, \quad y_2 = y_c + \sqrt{\Delta}$$

If \( \Delta \leq 0 \), there is no valid intersection.

---

## 4. Surface Geometry (Cross-Section)

### 4.1 Full Domain — \( z_{surface}(y) \)

Trapezoidal embankment, centreline at \( y = 0 \):

$$z_{surface}(y) = \begin{cases}
Z_{finish} & |y| \leq B_{top}/2 \\
Z_{finish} + t \cdot (z_{ground} - Z_{finish}) & B_{top}/2 < |y| \leq B_{base}/2 \\
z_{ground} & |y| > B_{base}/2
\end{cases}$$

where \( t = (|y| - B_{top}/2) / (B_{base}/2 - B_{top}/2) \) on the slope.

### 4.2 Half Domain — \( z_{surface\_half}(y) \) (One Side Slope)

Used when analysing one side (Left or Right) only:

**Right side** (\( y_{crest} = B_{top}/2 \), \( y_{toe} = B_{base}/2 \)):

$$z_{surface}(y) = \begin{cases}
Z_{finish} & y \leq y_{crest} \\
Z_{finish} + t \cdot (z_{ground} - Z_{finish}) & y_{crest} < y \leq y_{toe} \\
z_{ground} & y > y_{toe}
\end{cases}$$

with \( t = (y - y_{crest}) / (y_{toe} - y_{crest}) \).

**Left side** (mirror): \( y_{crest} = -B_{top}/2 \), \( y_{toe} = -B_{base}/2 \), with analogous linear interpolation.

---

## 5. Grid Search (Moment Method)

The grid search finds the **critical slip circle** (minimum FoS) by varying:

- **Centre x:** \( y_c \in [\text{grid\_x\_min}, \text{grid\_x\_max}] \), \( n_x \) steps
- **Centre z:** \( z_c \in [\text{grid\_z\_min}, \text{grid\_z\_max}] \), \( n_z \) steps  
- **Radius:** \( R \in [R_{min}, R_{max}] \), typically 120 steps

### 5.1 Geometry Validation Rules

A trial circle is **rejected** if:

| Rule | Condition |
|------|-----------|
| No intersection | \( \Delta = R^2 - (z_{ground} - z_c)^2 \leq 0 \) |
| Span (full mode) | Arc does not span base toes or top width (depending on span_mode) |
| Toe (half mode) | Arc does not pass near toe within tolerance |
| Behind crest (half mode) | Arc does not extend behind crest |
| Embankment (optional) | Arc does not pass through embankment within max_cover_height |
| Depth | \( z_c - R < z_{ground} - \text{max\_depth} \) or below bedrock |

### 5.2 Depth Constraint Modes

- **Limit below ground:** \( z_{min} \geq z_{ground} - \text{max\_depth\_below\_ground} \)
- **Limit below bedrock:** \( z_{min} \geq z_{bedrock} - \text{bedrock\_margin} \)

---

## 6. Output Quantities

### 6.1 φ = 0 Method

| Quantity | Formula / Description |
|----------|------------------------|
| FoS | \( F = \Sigma T_i / \Sigma D_i \) |
| ΣTi | Sum of resisting forces |
| ΣDi | Sum of driving forces |
| Slice table | b, z_surf, z_base, h, A_fill, A_clay, W, α (deg), sec, sin\|α\|, Ti, Di |

### 6.2 Moment Method

| Quantity | Formula / Description |
|----------|------------------------|
| FoS | \( F = M_{resist} / M_{drive} \) |
| M_drive | \( \Sigma W_i \cdot d_i \) |
| M_resist | \( c_u \cdot L_{arc} \cdot R \) |
| L_arc | Arc length (m) |
| W_total | Total weight of sliding mass |

---

## 7. Summary of Key Formulas

### φ = 0 Method (Primary)

$$F = \frac{\sum (c_u \cdot b \cdot \sec\alpha)}{\sum (W \cdot \sin|\alpha|)}$$

$$W = \gamma_{fill} A_{fill} + \gamma_{clay} A_{clay}$$

$$\alpha = \arctan\left(-\frac{x - x_c}{z_{base} - z_c}\right)$$

### Moment Method

$$F = \frac{c_u \cdot L_{arc} \cdot R}{M_{drive}}$$

$$M_{drive} = \sum W_i \cdot |y_{mid} - y_c|$$

$$L_{arc} = R \cdot 2\arcsin\left(\frac{\text{chord}}{2R}\right)$$

---

## 8. References in Code

| Function | Purpose |
|----------|---------|
| `phi0_slices_fos` | φ = 0 FoS calculation |
| `run_phi0_trials` | Runs 6 trial circles with φ = 0 method |
| `slope_stability_fos` | Moment-method FoS for single circle |
| `slope_stability_grid_search` | Grid search for critical circle (moment method) |
| `_roots_surface_minus_circle` | Finds slip arc entry/exit (x_L, x_R) |
| `_circle_ground_intersection` | Circle–ground intersection (y1, y2) |
| `_arc_length_lower` | Arc length of lower segment |
| `z_surface_half` | Surface elevation for half-domain |
| `_gamma_for_slice` | Unit weight selection per slice |

---

*Report generated from motorway design application codebase.*
