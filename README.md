# 🏨 Hsk Shadow PMS Automator

A lightweight, mobile-first interactive whiteboard and shadow PMS utility designed for hospitality operations. This application streamlines hotel housekeeping workflows by ingestion of raw property management system (PMS) exports, converting flat data into a real-time, high-density digital tracking board.

Originally built for operational deployment at **Best Western at Firestone**.

---

## 🚀 Key Features

* **Multi-Sheet Excel Parser:** Resilient backend engine that handles multi-sheet (`Sheet1`, `Sheet2`) daily data pulls without layout distortion.
* **Spatial Slicing (Hard-Wired Engine):** Uses structural grid-positioning (`pandas`) to precisely extract room inventory, room types, and statuses even when floating report headers misalign.
* **Mobile-First High-Density UI:** Custom CSS overrides injected into native Streamlit components to achieve a compact, high-density layout tailored for fast-paced mobile environments.
* **Live Room Spawning & Logging:** Ad-hoc manual entry system to register unexpected mid-day guest turnarounds or walk-ins instantly.
* **Real-Time Micro-Notes:** Inline communication field per room card allowing floor staff to log operational roadblocks (e.g., "towels only", "dog barking") with instant state preservation.

---

## 🎛️ The Operational Matrix Mapping

The core layout translates standard property management statuses into a 4-row matrix controller designed for rapid thumb-tapping on mobile devices:

| Code Selector | State Options | Operational Metric |
| :--- | :--- | :--- |
| **Occupancy** | `O` (Occupied) \| `V` (Vacant) | Tracks physical key handbacks |
| **Cleanliness**| `D` (Dirty) \| `C` (Clean) | Live room turn tracking |
| **Workload** | `F` (Flip Clean) \| `S` (Stayover) | Defines scope of service required |
| **Bumper** | `🛑 DnD` \| `⚪ Clear` | Hard-stop safety toggle for Do Not Disturb signs |

---

## 🛠️ Tech Stack & Architecture

* **Language:** Python
* **Framework:** Streamlit (Custom HTML/CSS injection via `unsafe_allow_html`)
* **Data Pipeline:** Pandas (Excel engine reading grids as pure string states)
* **State Management:** Streamlit Session State (`st.session_state`) for live data persistence across interactions

---

## 📦 Quick Start & Deployment

### Local Development
1. Clone the repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git)
   cd YOUR_REPO_NAME
