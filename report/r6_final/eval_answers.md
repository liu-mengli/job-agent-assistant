## Q0: Run Page有哪些执行模式和执行状态？

根據《3200 Optimized User Manual V1.2.doc》**1. Run Page (生產執行操作頁面)** 章節，Run Page 上的執行模式與執行狀態如下：

---

### 執行模式 (共 4 種)
- **On Line / Normal**
- **Off Line / Normal**
- **Off Line / No Device**
- **Off Line / No Device No Tray**

### 執行狀態 (共 6 種)
- **UnInitial**
- **Ready**
- **Cycle**
- **Cycle Stop**
- **One Cycle**
- **One Cycle Stop**

---

> 來源：上述資訊摘錄自《3200 Optimized User Manual V1.2.doc》「1. Run Page (生產執行操作頁面)」章節。

---

## Q1: Offset Setting的操作步骤是什么？

根據《3200 Optimized User Manual V1.2.doc》3.1 Offset Setting (各軸位置修正設定)章節，Offset Setting 的操作步驟如下：

1. **進入 Offset 頁面**：在機台的 Setup Page (設定工程師操作頁面) 中找到 Offset Setting 功能入口。
2. **選擇要修正的區域**：根據實際需要調整的軸，選擇對應的偏移設定分頁，例如：
   - Front Arm Stack & Fix Tray Offset
   - Front Arm Rotator Offset
   - Front Arm Trolley#1~#4 Offset
   - Back Arm Stack & Fix Tray Offset
   - Back Arm Rotator Offset
   - Back Arm Trolley#1~#4 Offset
   - Test Site Contact Trolley#1~#4 Offset
   - TS In Shuttle Offset
   - Rotator Offset
   - Tray Transfer Offset
   - Test Arm Force
3. **輸入偏移值**：在各欄位中輸入所需修正的偏移量（單位為 mm 或 Deg），例如 Pick X、Pick Y、Pick Z、Place X、Place Y、Place Z 等，方向以機台正面為主。
4. **儲存設定**：點選該頁面的 **Save** 按鈕，將目前 Offset 欄位資料儲存。
5. **關閉頁面**：點選 **Close** 按鈕，離開 Offset 頁面。

> 如需調整 Rotator 旋轉角度，需在「Rotator Offset」頁面設定 Angle 值（單位 Deg）。所有偏移值單位均為 mm（除 Angle 為 Deg）。

**注意事項**：調整前請確認 Robot 吸/放貨位置的實際誤差方向，微調數值後務必儲存，避免設定遺失。

---

## Q2: 如何进行Auto Alignment自动校准？

⚠️ **注意**：自動位置校正涉及機台原點設定，操作錯誤可能影響機台運作。請由受過訓練的人員操作，詳見第 3.5 章節說明。

根據《3200 Optimized User Manual V1.2.doc》第 4.14 章節，進行 Auto Alignment (自動位置校正) 的操作步驟如下：

1. **進入校正頁面**  
   在 Engineer Page (系統工程師操作頁面) 找到並點選 Auto Alignment 功能。

2. **選擇校正類型**  
   可選擇 **Robot**、**Motor** 或 **Lidar** 位置校正（視需要校正的項目而定）。若需全部校正，可點選 **Select All**（選擇全部位置）。

3. **執行校正動作**  
   - 點選 **Alignment Start**（自動進行原點校正），系統即開始自動校正流程。  
   - 若需中途停止，可點選 **Alignment Stop**（停止 Alignment 動作）。

4. **針對個別 Robot 初始化（選擇性）**  
   - **Robot Initial Start**：單獨對 Robot 進行 Initial（初始化）動作。  
   - **Robot Initial Start**（按鈕名稱重複，原文標示為「停止 Initial 動作」）：點選可停止 Initial 動作。（請注意原文此處可能有標示不一致，實際操作時以介面按鈕功能為準。）

5. **完成並離開**  
   校正完成後，點選 **Close** 關閉 Alignment 頁面。

> 來源：《3200 Optimized User Manual V1.2.doc》4. Engineer Page > 4.14 Auto Alignment 章節

---

## Q3: 操作3200设备时有哪些安全注意事项？

⚠️ **安全注意事項——必須嚴格遵守**

根據《3200 Optimized User Manual V1.2.doc》「安全概要」章節，操作3200設備時應注意以下安全要點：

1. **接上電源之前**：檢查電源符合本電源供應器之額定輸入值。
2. **保護接地**：開啟電源前，請確定連接保護接地以預防電擊。
3. **保護接地的必要性**：勿切斷內部或外側保護接地線或中斷保護接地端子的連接，否則將引起潛在電擊危險，可能對人體帶來傷害。
4. **保險絲**：僅可使用所需額定電流、電壓及特定形式的保險絲（正常的熔絲、時間延遲等），勿使用不同規格或短路保險絲座，否則可能引起電擊或火災的危險。
5. **勿於易爆的空氣下操作**：勿操作儀器於易燃瓦斯或氣體之下，儀器應在通風良好的環境下使用。
6. **勿拆掉儀器的外殼**：操作人員不可拆掉儀器的外殼，零件的更換及內部的調整僅可由合格的維修人員來執行。

此外，手冊中於「前端控制面板」章節亦備註：  
※機台於生產中不得任意放置料盤於入料盤區與空料盤區。  
※當機台未執行 Initial 動作時，Start 鈕將不會亮起，代表機台未處於待命狀態。  
※當馬達執行過 Servo Off 動作時，機台必須執行 Initial 動作。

如遇任何異常或錯誤，請先排除問題後再按下對應按鈕（如 Reset、Retry、Skip）進行後續操作，切勿強行繼續。

---

## Q4: User Page和Engineer Page的Yield Control良率控制有什么区别？

根據檢索結果，**User Page**（作業員操作頁面）與**Engineer Page**（系統工程師操作頁面）的 **Yield Control** 設定在以下方面存在差異：

| 功能項目 | User Page 行為 | Engineer Page 行為 | 來源 |
|----------|---------------|-------------------|------|
| **Fail Setting** （連續Fail處理） | 當測試連續Fail達到Fail Count數量時，**機台停機並Alarm**，按下Reset後清除歸零。 | 當測試連續Fail達到Fail Count數量時，**將強制關閉該Site**，機台停機並Alarm，按下Reset後清除歸零。 | User: 《3200 Optimized User Manual V1.2.doc》2.3；Engineer: 4.4 |
| **Pass Setting** （連續Pass處理） | 當測試連續Pass達到該Site所設定的數量時，**機台停機並Alarm**，按下Reset後清除歸零。 | 當測試連續Pass達到該Site所設定的數量時，**系統才視為該Site為能生產的測試程序**（無停機警報動作）。 | User: 《3200 Optimized User Manual V1.2.doc》2.3；Engineer: 4.4 |
| **Yield Setting** （良率控制） | 程式計算最近“Control Window”顆數的良率，若低於Yield Limitation，機台停機並Alarm；**每個Site的目前監控良率顯示於Control Window Yield視窗內**。 | 程式計算最近“Control Window”顆數的良率，若低於Yield Limitation，機台停機並Alarm；**Control window Yield顯示目前測試良率**（未提及逐Site顯示）。 | User: 《3200 Optimized User Manual V1.2.doc》2.3；Engineer: 4.4 |
| **Save / Cancel** | 儲存/離開功能相同 | 儲存/離開功能相同 | 兩者皆相同 |

**關鍵差異總結：**
1. **Fail Setting** — Engineer Page 在連續Fail時會額外**強制關閉該Site**，比User Page多了一層硬體保護。
2. **Pass Setting** — User Page中**連續Pass達到數量會觸發停機警報**（可能用於提示或強制檢查），而Engineer Page則是**將該Site視為可生產狀態**，無停機動作，行為完全不同。
3. **Yield Setting** — User Page明確說明**逐Site顯示當前良率於視窗**，Engineer Page僅提「顯示目前測試良率」，細節表述略有不同，但核心邏輯一致。

> 注意：User Page中段有一段關於IC吸取方式（Drop High / Drop Timer）的描述，屬於文檔排版插入的其他設定，非Yield Control內容，請勿混淆。

若需進一步了解各功能的使用時機，建議參考《3200 Optimized User Manual V1.2.doc》中對應章節的完整說明。

---

## Q5: Timer Setting怎么设置，有哪些参数？

根据《3200 Optimized User Manual V1.2.doc》的 **4.3 Timer Setting (時間設定)** 章节，Timer Setting 頁面提供使用者設定部分動作所需花費的時間。設定方式為：在該頁面中直接修改各欄位的數值，然後點選 **Save** 按鈕儲存設定；若需恢復預設值，可點選 **Default**；完成後點選 **Close** 離開頁面。

以下為該頁面包含的所有參數及其說明：

| 參數名稱 | 內容說明 | 建議值 / 備註 |
| --- | --- | --- |
| **Vacuum Timeout** | 程式在吸IC過程中，只要 Vacuum Sensor ON 就會進入下一個動作；若超過此時間且Vacuum Sensor未ON，機台會停止並Alarm。 | 建議設 **4 Sec**。 |
| **Vacuum Delay** | 手臂移動到位後，需停留的時間，程式會等待所設定的時間後才開 Vacuum。 | 依實際需求調整。 |
| **Vacuum Stable** | Vacuum Sensor ON 後，等待穩定時間，程式會等待所設定的時間後才會執行下一個動作。 | 依實際需求調整。 |
| **Blow Delay** | 手臂移動到位後，需停留的時間，程式會等待所設定的時間後才會關 Vacuum & 開 Blow。 | 依實際需求調整。 |
| **Blow Time** | 吹氣時間，程式會等待所設定的時間後才進行下一個動作。 | 建議不要太大。 |
| **Blow Stable** | Blow Time 後，等待穩定時間，程式會等待所設定的時間後才會執行下一個動作。 | 依實際需求調整。 |
| **Down Time** | Input Arm Z 軸下降時間。 | 依實際需求調整。 |
| **Up Time** | Input Arm Z 軸上升時間。 | 依實際需求調整。 |

**操作步驟：**
1. 進入 Engineer Page 的 **Timer Setting** 頁面。
2. 根據實際需求修改上述任一參數數值。
3. 點選 **Save** 儲存設定。
4. 若想恢復出廠預設值，可先點選 **Default** 再儲存。
5. 完成後點選 **Close** 離開頁面。

⚠️ 注意：**Vacuum Timeout** 建議設為 4 Sec，**Blow Time** 建議不要設定太大，以免影響機台效率。

以上資訊來源：《3200 Optimized User Manual V1.2.doc》4.3 Timer Setting 章節。

---

## Q6: IO Monitor和Motor Monitor分别有什么功能？

根據知識庫中的資料，IO Monitor 與 Motor Monitor 的功能整理如下：

## IO Monitor（IO 監視器）

**功能**：此功能可用以監看各 IO 點目前的狀態。燈號圖示紅色為 Input（輸入），綠色為 Output（輸出）。Output 可以手動點選開關，暗色表示此狀態 Off，亮色表示此狀態 On。離開此畫面後，IO 會回復為原來的狀態。

- 提供一個「Close」按鈕，點選後離開頁面。

根據《3200 Optimized User Manual V1.2.doc》3. Setup Page > 3.3 IO Monitor 章節

---

## Motor Monitor（馬達監視器）

**功能**：此功能用以監看馬達的狀態燈號，各狀態燈號說明如下表：

| 名稱  | 說明 | 備註 |
|-------|------|------|
| Alarm | 馬達故障，請按 Reset 清除並 Initial 機台。 |  |
| Drive | 命令訊號，ON 表示馬達正被驅動中。 |  |
| EMG  | 急停訊號。 |  |
| Error | 正、負極限是否動作的訊號。 |  |
| InPos | 馬達是否到位訊號。 |  |
| LMT- | 負極限，ON 表示位置已達負極限。 |  |
| LMT+ | 正極限，ON 表示位置已達正極限。 |  |
| TLC  | Torque Limit Control，ON 表示 Torque 達到限制值。 |  |

（註：3.4 章節中另包含 Z-Phase 馬達原點是否到位訊號，4.1 章節無 Z-Phase）

- 提供一個「Close」按鈕，點選後離開 Motor Monitor 頁面（或 Site Setting 頁面，視版本而定）。

根據《3200 Optimized User Manual V1.2.doc》3. Setup Page > 3.4 Motor Monitor 章節 及 4. Engineer Page > 4.1 Motor Monitor 章節

---

**總結**：IO Monitor 用於監看與手動控制 IO 點（輸入/輸出）的即時狀態；Motor Monitor 用於監看馬達相關的狀態訊號（如故障、驅動、極限、急停等），不提供手動控制功能。兩者均可透過 Close 按鈕離開頁面。

---

## Q7: Tray File料盘资料和Tray Map有什么不同？

根據知識庫內容，Tray File（料盤資料）與 Tray Map（料盤地圖）是兩個不同用途的功能，主要差異如下：

| 項目 | Tray File（料盤資料） | Tray Map（料盤地圖） |
|------|----------------------|----------------------|
| **所在頁面** | Engineer Page（系統工程師操作頁面） | Run Page（生產執行操作頁面）及 User Page（作業員操作頁面） |
| **主要功能** | 管理料盤資料（新增/刪除/修改），設定料盤尺寸規格（如縱列個數、横列個數、相鄰Device距離、IC長寬、LiDar偵測距離等） | 記錄或顯示料盤上每個位置的IC資訊（Barcode、Bin Code、測試結果）或取放狀態 |
| **用途** | 定義料盤的物理規格與感測器參數，供生產時使用 | 追蹤IC在料盤上的位置資訊，便於查詢測試結果或監控取放狀態 |
| **關鍵參數** | Col、Row、A、B、C、D、H、W、High、Low、Tray Type、Lidar detect、SLT Program | Output Tray Map：記錄Device Barcode、Bin Code、Test Result；Input Tray Map：顯示已取/未取狀態 |
| **儲存限制** | 無特別說明 | Output Tray Map 每個Stack最多儲存100筆資料，滿則覆蓋最舊資料；Lot Done後清除 |

**總結**：
- **Tray File** 是用來**設定料盤的幾何尺寸與感測器參數**，屬於事前配置。
- **Tray Map** 是用來**記錄或顯示料盤上實際IC的測試資訊或取放狀態**，屬於生產過程中的即時追蹤。

參考來源：
- Tray File 說明：根據《3200 Optimized User Manual V1.2.doc》4. Engineer Page > 4.5 Tray File 章節
- Tray Map（Output）：根據《3200 Optimized User Manual V1.2.doc》1. Run Page > 1.4 Output Tray Map 章節
- Tray Map（Input）：根據《3200 Optimized User Manual V1.2.doc》2. User Page > 2.1 Input Tray Map 章節

---

## Q8: Cobra温度控制怎么设定？

根据《3200 Optimized User Manual V1.2.doc》3.11 Cobra (溫度控制設定) 章节，Cobra 溫度控制設定操作如下：

1. 在設定工程師操作頁面中，找到 **3.11 Cobra (溫度控制設定)** 頁面。
2. 選擇 **Set SV** 選項，設定溫控器的目標溫度值。
3. 頁面上會顯示：
   - (2)：目前溫度設定值（即剛設定的 SV 值）
   - **TC1**：溫控器目前量測到的實際溫度值
   - **Evap**：溫控器蒸發器溫度值
4. 設定完成後，點選 **Close** 離開此頁面。

> 注意：此頁面為工程師操作頁面，僅可設定目標溫度（Set SV），其他欄位為唯讀顯示。

---

## Q9: Event Log事件记录在哪几个页面可以看到，有什么不同？

Event Log（事件記錄）功能可在以下三個頁面中查看，其差異主要在於對應的操作權限與可進行的設定範圍：

1. **Run Page（生產執行操作頁面）**  
   - 位置：此頁面中有一個「Event Log」按鈕，點選後可檢視事件記錄。  
   - 權限：此頁面為生產執行畫面，通常供 User（使用者）模式操作，僅能**瀏覽**事件記錄，無法進行進階篩選或設定。  
   來源：根據《3200 Optimized User Manual V1.2.doc》1. Run Page (生產執行操作頁面)章節。

2. **Setup Page（設定工程師操作頁面）**  
   - 位置：3.7 Event Log 章節，提供完整的事件記錄檢視介面。  
   - 功能：包含時間區間選取、Export 匯出報表（.csv）、異常等級顯示設定（Operating record / Staff / Produce / Machinery）、Default Event 顯示最新列表等。  
   - 權限：對應 Setup（設定工程師）模式，可進行事件篩選與匯出。  
   來源：根據《3200 Optimized User Manual V1.2.doc》3. Setup Page (設定工程師操作頁面) > 3.7 Event Log 章節。

3. **Engineer Page（系統工程師操作頁面）**  
   - 位置：4.11 Event Log 章節，功能與 Setup Page 完全相同（時間區間選取、Export、Event Log Selection For Display、Default Event）。  
   - 權限：對應 Engineer（系統工程師）模式，與 Setup Page 的差異僅在於所屬頁面層級不同，實際操作功能一致。  
   來源：根據《3200 Optimized User Manual V1.2.doc》4. Engineer Page (系統工程師操作頁面) > 4.11 Event Log 章節。

**總結差異**：  
- Run Page 僅提供**進入 Event Log 的按鈕**，無篩選或匯出功能，主要供一般操作人員快速查看。  
- Setup Page 與 Engineer Page 具有**完整的事件記錄管理功能**（時間篩選、等級分類、匯出），差別在於需要對應的工程師權限才能進入該頁面。  

> ⚠️ 注意：若您無法在 Run Page 中進行進階操作，請切換至 Setup 或 Engineer 模式以使用完整功能。

---

