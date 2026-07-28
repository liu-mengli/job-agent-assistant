## Q0: Run Page有哪些执行模式和执行状态？

根據《3200 Optimized User Manual V1.2.doc》1. Run Page (生產執行操作頁面)章節，Run Page 的執行模式與執行狀態如下：

**執行模式：**
- On Line/Normal
- Off Line/Normal
- Off Line/No Device
- Off Line/ No Device No Tray

**執行狀態：**
- UnInitial
- Ready
- Cycle
- Cycle Stop
- One Cycle
- One Cycle Stop

以上資訊依據文件原文，請於實際操作時確認畫面顯示的當前狀態。

---

## Q1: Offset Setting的操作步骤是什么？

根據《3200 Optimized User Manual V1.2.doc》3.1 Offset Setting (各軸位置修正設定) 章節，Offset Setting 的操作步驟如下：

1. **進入 Offset 頁面**  
   在 Setup Page (設定工程師操作頁面) 中開啟 Offset Setting 頁面。

2. **依需求選擇要調整的區域**  
   頁面包含以下區域，請根據需要調整對應的 Offset 值（單位：mm）：
   - **Front Arm Stack & Fix Tray Offset**：調整 Place X、Place Y、Place Z（適用 Stack 1~6、Fix Tray 1~6 的 Place 動作）。
   - **Front Arm Rotator Offset**：調整 Pick X、Pick Y、Pick Z、Place X、Place Y、Place Z（適用 Rotator 1、2 的 Pick/Place 動作）。
   - **Front Arm Trolley#1~#4 Offset**：調整 Pick X、Pick Y、Pick Z（適用 Front Arm Trolley#1~#4 的 Pick 動作）。
   - **Back Arm Stack & Fix Tray Offset**：調整 Pick X、Pick Y、Pick Z（適用 Stack 1~6、Fix Tray 1~6 的 Pick 動作）。
   - **Back Arm Rotator Offset**：調整 Pick X、Pick Y、Pick Z、Place X、Place Y、Place Z（適用 Rotator 的 Pick/Place 動作）。
   - **Back Arm Trolley#1~#4 Offset**：調整 Pick X、Pick Y、Pick Z、Place X、Place Y、Place Z（適用 Stack 1~6、Fix Tray 1~6 的 Pick/Place 動作）。
   - **Test Site Contact Trolley#1~#4 Offset**：調整 Contact Z（Contact 深度 Offset）。
   - **TS In Shuttle Offset**：調整 Shuttle In（Pick 深度 Offset）及 Shuttle Out（Place 深度 Offset），適用 Trolley 1~4 每 Site。
   - **Rotator Offset**：調整 Angle（旋轉角度 Offset，單位：Deg）。
   - **Tray Transfer Offset**：調整 Pick X、Place X（適用 Empty 1、2、Stack 1~6 的 Pick/Place 動作）。
   - **Test Arm Force**：調整 Set Value（力量值，單位：Kg，適用 Trolley 1~4 內各 Site）。

3. **輸入修正值**  
   在各欄位中輸入所需的 Offset 數值（單位 mm，除 Angle 為 Deg、Force 為 Kg）。

4. **儲存設定**  
   點選 **Save** 按鈕，將目前 Offset 欄位資料作儲存動作。

5. **關閉頁面**  
   點選 **Close** 按鈕，離開 Offset 頁面。

**注意事項**：所有 Offset 調整應以機台正面為主，僅對吸/放貨位置的微小誤差進行微調。

---

## Q2: 如何进行Auto Alignment自动校准？

根據《3200 Optimized User Manual V1.2.doc》4.14 Auto Alignment (自動位置校正) 章節，進行 Auto Alignment 自動位置校正的操作步驟如下：

1. **選擇要校正的對象**  
   在 Alignment 頁面中，可選擇 **Robot**、**Motor** 或 **Lidar** 位置校正。當手臂位置錯誤過大（例如因拆裝組件造成）時，可利用此功能重新設定位置。

2. **Robot Initial Start（單獨對 Robot 進行初始歸位）**  
   點選「Robot Initial Start」按鈕，開始執行 Robot 的初始動作。若要停止此動作，則點選「Robot Initial Start」旁的停止按鈕（原文未明確命名，但描述為「停止 Initial 動作」）。

3. **Select All（選擇全部位置）**  
   點選「Select All」，選取所有需要校正的位置。

4. **Alignment Start（自動進行原點校正）**  
   點選「Alignment Start」按鈕，系統會自動執行原點校正動作。

5. **Alignment Stop（停止 Alignment 動作）**  
   若要中途停止校正，點選「Alignment Stop」按鈕。

6. **Close（離開頁面）**  
   校正完成後，點選「Close」離開 Alignment 頁面。

⚠️ **注意事項**：此功能主要用於手臂位置錯誤過大時（例如拆裝組件後）重新設定位置，請確認操作環境安全。

---

## Q3: 操作3200设备时有哪些安全注意事项？

⚠️ **操作 3200 设备时，必须严格遵守以下安全注意事项：**

根据《3200 Optimized User Manual V1.2.doc》**安全概要**章节：

- **接上电源之前**：检查电源符合本电源供应器之额定输入值。
- **保护接地**：开启电源前，请确定连接保护接地以预防电击。
- **保护接地的必要性**：切勿切断内部或外侧保护接地线或中断保护接地端子的连接，否则将引起潜在电击危险，可能对人体带来伤害。
- **保险丝**：仅可使用所需额定电流、电压及特定形式的保险丝（正常的熔丝、时间延迟等）。勿使用不同规格的保险丝或短路保险丝座，否则可能引起电击或火灾的危险。
- **勿于易爆的空气下操作**：勿操作仪器于易燃瓦斯或气体之下，仪器应在通风良好的环境下使用。
- **勿拆掉仪器的外壳**：操作人员不可拆掉仪器的外壳。零件的更换及内部的调整仅可由合格的维修人员来执行。

根据同一文档**安全符号**章节：

- ⚡ **高压危险**：当出现高压符号时，为避免伤害、人员死亡或对仪器的损害，操作者必须参考手册中的说明。
- 🔥 **高温**：当见高温符号，代表此处温度高于人体可接受范围，勿任意接触，避免人员伤害。
- ⛓️ **保护接地端子**：若有失误的情形下保护以防止电击。此符号表示仪器操作前端子必须连接至大地。
- ⚠️ **警告**：标记表示危险，用来提醒使用者注意若未依循正确的操作程序，可能会导致人员伤害。在完全了解及执行须注意的事项前，切勿忽视警告标记并继续操作。
- 💡 **提示**：注意标示，程序、应用或其他方面的重要资料，请特别详读。

**总结**：操作前务必确认电源规格、接地连接、保险丝规格，严禁在易燃环境中使用，禁止私自拆卸外壳。任何异常应先排除错误后再操作，确保人身与设备安全。

---

## Q4: User Page和Engineer Page的Yield Control良率控制有什么区别？

根据检索到的内容，**User Page（作業員操作頁面）** 與 **Engineer Page（系統工程師操作頁面）** 的 Yield Control 設定在功能描述上存在以下關鍵差異：

| 對比項目 | User Page（作業員） | Engineer Page（系統工程師） |
|:---:|:---:|:---:|
| **Fail Setting 行為** | 當測試連續 Fail 達到 Fail Count 數量時，**機台停機並 Alarm**，按下 Reset 後清除歸零。未提及關閉 Site。 | 當測試連續 Fail 達到 Fail Count 數量時，**強制關閉該 Site**，機台停機並 Alarm，按下 Reset 後自動清除歸零。 |
| **Pass Setting 行為** | 當測試連續 Pass 達到該 Site 設定的數量時，**機台停機並 Alarm**，按下 Reset 後清除歸零。 | 當測試連續 Pass 達到該 Site 設定的數量時，**系統才視為該 Site 為能生產的測試程序**（並非停機 Alarm）。 |
| **Yield Setting 顯示** | 未顯示目前測試良率數值。 | 明確提供 **Control window Yield** 顯示目前測試良率。 |
| **額外內容** | 章節末尾包含一段關於「IC 被測試頭吸取後直接進入 Socket」與「Drop High 模式」的文字（疑似錯置或附加說明），與 Yield Control 設定無關。 | 無此段文字，內容純粹專注於 Yield 控制設定。 |

**總結關鍵差異點：**

1. **Fail 處理機制**：Engineer 頁面會「強制關閉該 Site（測試座）」，而 User 頁面僅停機 Alarm，不關閉 Site。
2. **Pass 判斷邏輯**：Engineer 頁面中 Pass Setting 是用來「判定該 Site 可正常生產」，並非觸發停機；User 頁面則錯誤地將 Pass 達到數量也視為停機 Alarm 條件（可能為文件版本或權限差異）。
3. **良率即時顯示**：Engineer 頁面提供 Control window Yield 數值，User 頁面無此顯示。
4. **操作者權限**：Engineer 頁面包含完整的 Fail/Pass/Yield 控制設定，且行為更貼近「系統工程師監控並自動關閉不良 Site」的邏輯；User 頁面則簡化為單純的停機報警。

如果需要進一步了解各設定的實際操作影響，建議以 Engineer 頁面的描述為準（因其權限較高且邏輯更完整）。

根據《3200 Optimized User Manual V1.2.doc》之「2.3 Yield Control (良率控制設定)」與「4.4 Yield Control (良率控制設定)」章節。

---

## Q5: Timer Setting怎么设置，有哪些参数？

根據《3200 Optimized User Manual V1.2.doc》4. Engineer Page (系統工程師操作頁面) > 4.3 Timer Setting (時間設定)章節，Timer Setting 提供使用者設定各動作花費的時間，參數及建議值如下：

| 欄位名稱 | 內容說明 | 建議/預設值參考 |
| --- | --- | --- |
| Vacuum Timeout | 吸IC過程中，超過設定時間且Vacuum Sensor未ON，機台將停止並Alarm。 | 建議放4 Sec |
| Vacuum Delay | 手臂移動到位後，停留時間，等待設定時間後才開 Vacuum。 | 無預設建議 |
| Vacuum Stable | Vacuum Sensor ON後，等待穩定時間，才執行下一個動作。 | 無預設建議 |
| Blow Delay | 手臂移動到位後，停留時間，等待設定時間後才關 Vacuum & 開 Blow。 | 無預設建議 |
| Blow Time | 吹氣時間，等待設定時間後才進行下一個動作。 | 建議不要太大 |
| Blow Stable | Blow Time 後，等待穩定時間，才執行下一個動作。 | 無預設建議 |
| Down Time | Input Arm Z 軸下降時間。 | 無預設建議 |
| Up Time | Input Arm Z 軸上升時間。 | 無預設建議 |

**設定操作方式：**
1. 進入 Timer Setting 頁面後，直接在各欄位文字框中輸入所需的秒數。
2. 點擊 **Default** 按鈕可將所有時間設定值恢復為預設值。
3. 點擊 **Save** 儲存所有設定值。
4. 點擊 **Close** 離開該頁面。

⚠️ 注意：Vacuum Timeout 建議設為 4 秒，Blow Time 建議不要設定過大，以免影響整體節拍。所有設定完成後務必點擊 Save 才能生效。

---

## Q6: IO Monitor和Motor Monitor分别有什么功能？

根據知識庫內容，IO Monitor 與 Motor Monitor 的功能說明如下：

---

### **IO Monitor（IO 監視器）**
- **功能**：用以監看各 IO 點目前的狀態。燈號圖示紅色代表 Input，綠色代表 Output。Output 可以手動點選開關，暗色表示該狀態 Off，亮色表示 On。離開此頁面後，IO 會回復為原來的狀態。
- **操作**：提供關閉頁面按鈕（Close）。

### **Motor Monitor（馬達監視）**
- **功能**：用以監視各馬達的狀態，透過燈號顯示以下訊號：
  - **Alarm**：馬達故障，須按 Reset 清除並 Initial 機台。
  - **Drive**：命令訊號，ON 表示馬達正被驅動中。
  - **EMG**：急停訊號。
  - **Error**：正、負極限是否動作的訊號。
  - **InPos**：馬達是否到位訊號。
  - **LMT-**：負極限，ON 表示位置已達負極限。
  - **LMT+**：正極限，ON 表示位置已達正極限。
  - **Z-Phase**（僅在 3.4 節列出）：馬達原點是否到位訊號。
  - **TLC**：Torque Limit Control，ON 表示 Torque 達到限制值。
- **操作**：提供關閉頁面按鈕（Close）。

---

**根據《3200 Optimized User Manual V1.2.doc》3.3 IO Monitor（IO 監視器）章節及 3.4/4.1 Motor Monitor（馬達監視）章節。**

---

## Q7: Tray File料盘资料和Tray Map有什么不同？

根據知識庫的內容，**Tray File（料盤資料）** 與 **Tray Map** 在功能、用途和管理對象上均有明顯差異。以下以對比表格說明：

| 對比項 | Tray File（料盤資料） | Tray Map |
|--------|----------------------|----------|
| **功能定位** | 管理料盤的幾何尺寸、偵測參數及生產關聯設定（如 SLT Program） | 記錄料盤上每一個 IC 的實際狀態（取放狀態或測試結果） |
| **使用場景** | 「工程師頁面（Engineer Page）」→ 4.5 Tray File | 分為「Input Tray Map」（作業員頁面）與「Output Tray Map」（生產執行頁面） |
| **設定內容** | 行列個數（Col/Row）、間距（A/B/C/D）、IC 尺寸（H/W）、LiDar 偵測高低位、Tray Type、SLT Program 等 | Input Tray Map：顯示每個位置是否已取過 IC（綠色/灰色）<br>Output Tray Map：記錄每個位置的 Device Barcode、Bin Code、測試結果（Pass/Fail） |
| **操作行為** | 新增、修改、刪除料盤設定檔，並可儲存或取消 | Input Tray Map：可整區圈選切換狀態、Clear All 重置、儲存當前狀態<br>Output Tray Map：自動記錄，最多儲存 100 筆，Lot Done 後清除 |
| **數據性質** | 靜態設定參數（定義料盤本身的物理屬性及生產關聯） | 動態執行記錄（即時反映 IC 的取放或測試結果狀態） |

### 關鍵差異總結
- **Tray File** 是「料盤的規格定義」，告訴機器這個料盤長什麼樣子、如何偵測、對應哪個測試程式。
- **Tray Map** 是「料盤上每個位置的實際狀態」，在 Input 側用來追蹤哪些 IC 已取用，在 Output 側用來查詢每個 IC 的測試結果與條碼資訊。

> 根據《3200 Optimized User Manual V1.2.doc》4.5 Tray File、2.1 Input Tray Map、1.4 Output Tray Map 章節整理。

---

## Q8: Cobra温度控制怎么设定？

根據《3200 Optimized User Manual V1.2.doc》3.11 Cobra (溫度控制設定)章節，Cobra 溫度控制設定步驟如下：

1. **Set SV**：設定溫控器的目標溫度值（即您想要達到的溫度）。
2. **查看目前溫度設定值**：確認溫控器當前的溫度設定值是否正確。
3. **TC1**：檢視溫控器目前實際量測到的溫度值。
4. **Evap**：查看溫控器蒸發器的溫度值。
5. **Close**：設定完畢後，點選「Close」離開此頁面。

⚠️ 注意：此頁面僅供讀取與設定溫度相關數值，若需修改溫度設定，請在 Set SV 欄位輸入正確的目標溫度。相關操作請由受過訓練的人員執行。

---

## Q9: Event Log事件记录在哪几个页面可以看到，有什么不同？

根據知識庫內容，Event Log（事件記錄）可在 **Run Page（生產執行操作頁面）**、**Setup Page（設定工程師操作頁面）** 以及 **Engineer Page（系統工程師操作頁面）** 中看到。

---

### 各頁面中的Event Log差異

| 頁面 | 出現形式 | 功能說明 |
|------|----------|----------|
| **Run Page** | 僅為一個按鈕或入口圖示 | 根據《3200 Optimized User Manual V1.2.doc》1. Run Page章節記載，Run Page上有一個「Event Log」按鈕，但未提供該頁面的詳細操作描述，僅作為快速進入事件記錄的途徑。 |
| **Setup Page** | 獨立章節（3.7 Event Log） | 提供完整的Event Log操作介面，包含時間區間選取、Export匯出（.csv檔）、事件等級篩選（Operating record / Staff / Produce / Machinery）、Default Event顯示最新列表等功能。 |
| **Engineer Page** | 獨立章節（4.11 Event Log） | 內容與Setup Page完全相同，同樣具備時間區間查詢、Export匯出（.txt檔，但說明中寫.csv檔）、等級篩選、Default Event等功能。 |

> **關鍵差異總結**：  
> - **Run Page** 僅是一個入口按鈕，不提供查詢、篩選、匯出等操作介面。  
> - **Setup Page** 與 **Engineer Page** 則包含完整的事件記錄管理功能，兩者的功能描述幾乎一致。差異可能僅在於使用者權限等級（Setup模式與Engineer模式），但文件中未明確說明不同等級下功能是否有差別。

---

