classdef microinject_gui < handle
    % MICROINJECT_GUI — Precise MATLAB replica of the Python Microinjector GUI
    % 
    % Reproduces all functions: Manual Move (mm/uL), Program Editor (Max 5 steps),
    % Syringe calibration (nL/uL/mL), and Serial Console Logging.
    % 
    % Requirements: Instrument Control Toolbox
    
    properties (Access = private)
        % UI Framework
        Figure
        Grid
        TabGroup
        ManualTab
        ProgramTab
        SyringeTab
        
        % Top Bar
        PortCombo
        BaudCombo
        ConnectBtn
        StatusLabel
        MotorStatusLabel
        CountdownLabel
        
        % Manual Tab
        ManUnitStepsRb
        ManUnitUlRb
        ManUlBadge
        ManDirFwdRb
        ManDirBwdRb
        ManDistSpin
        ManRevLabel
        ManTimeS_Rb
        ManTimeMin_Rb
        ManStartSlider
        ManStartSpin
        ManStartUnit
        ManEndSlider
        ManEndSpin
        ManEndUnit
        ManAccelSlider
        ManAccelSpin
        ManAccelUnit
        ManDurationLabel
        ManRangeHintSpeed
        ManRangeHintAccel
        ManMoveBtn
        ManStopBtn
        ManJogSpeedSpin
        ManJogFwdBtn
        ManJogBwdBtn
        CountdownValue
        
        % Program Tab
        ProgTable
        ProgAddBtn
        ProgDelBtn
        ProgClearBtn
        ProgRunBtn
        ProgStopBtn
        ProgDurationLabel
        
        % Syringe Tab
        SyrPresetCombo
        SyrVolSpin
        SyrUnitCombo
        SyrStrokeSpin
        SyrUlStepLabel
        SyrStepUlLabel
        SyrConfirmChk
        ConvInputUlSpin
        ConvUlToStepsLabel
        ConvInputMmSpin
        ConvMmToUlLabel
        
        % Log Panel
        LogArea
        
        % Logic & Data
        SerialObj
        Program = struct('forward', {}, 'distance', {}, 'start_speed', {}, 'end_speed', {}, 'accel', {})
        MotorState = 'IDLE' % 'IDLE' or 'MOVING'
        UnitMode = 'mm' % 'mm' or 'ul'
        VolUnit = 'uL'
        VolScales = struct('nL', 1000.0, 'uL', 1.0, 'mL', 0.001)
        
        % Constants
        MM_PER_STEP = 0.8 / 2048
        STEPS_PER_MM = 2048 / 0.8
        
        CountdownTimer
    end
    
    properties (Access = private, Hidden)
        % Internal Logic State
        SyncingSpeed = false
        InProgMenu = false
        CmdQueue = {}
        ManualStepPending = []
        ProgStepPending = []
        JogActive = false

        % Radio Button Handles for Logic
        ManAccelS_Rb
        ManAccelMin_Rb
        ApplyingPreset = false   % guard: true while applying a preset
    end
    
    properties (Constant)
        % Colour Palette (Python Replica – modern dark)
        DARK_BG     = '#0f1117'
        PANEL_BG    = '#171b24'
        CARD_BG     = '#1e2330'
        ACCENT      = '#38bdf8' % sky blue
        ACCENT2     = '#818cf8' % indigo
        DANGER      = '#f87171'
        SUCCESS     = '#059669' % Darker emerald for better legibility with white text
        TEXT_PRI    = '#e2e8f0'
        TEXT_SEC    = '#7a8599'
        BORDER      = '#2a3040'
        
        % Hamilton 1700 series syringe presets: {label, volume_uL, stroke_mm}
        % All 1700-series models share the same 60 mm plunger stroke.
        HAMILTON_1700_PRESETS = {
            'Custom…',        [],    [];
            '1701 — 10 µL',   10.0,  60.0;
            '1702 — 25 µL',   25.0,  60.0;
            '1705 — 50 µL',   50.0,  60.0;
            '1710 — 100 µL',  100.0, 60.0;
            '1725 — 250 µL',  250.0, 60.0;
            '1750 — 500 µL',  500.0, 60.0;
        }
    end
    
    methods
        function obj = microinject_gui()
            obj.buildUI();
            obj.refreshPorts();
            
            % Setup Countdown Timer
            obj.CountdownTimer = timer('ExecutionMode', 'fixedRate', 'Period', 0.1, ...
                'TimerFcn', @(~,~) obj.onCountdownTick());
        end
        
        function delete(obj)
            stop(obj.CountdownTimer);
            delete(obj.CountdownTimer);
            if ~isempty(obj.SerialObj) && isvalid(obj.SerialObj), delete(obj.SerialObj); end
            if ~isempty(obj.Figure) && isvalid(obj.Figure), delete(obj.Figure); end
        end
        
        function disp(obj)
            fprintf('  microinject_gui object with Figure: %s\n', obj.Figure.Name);
            fprintf('  Run "delete(ans)" or "clear ans" to close.\n');
        end
    end
    
    methods (Access = private)
        function buildUI(obj)
            % Main Figure
            obj.Figure = uifigure('Name', 'Microinjector Control Panel', ...
                'Position', [100 100 1200 900], 'Color', obj.DARK_BG, ...
                'WindowKeyPressFcn',   @obj.onGlobalKey, ...
                'WindowKeyReleaseFcn', @obj.onGlobalKeyRelease, ...
                'WindowButtonDownFcn', @obj.onWindowButtonDown, ...
                'WindowButtonUpFcn',   @obj.onWindowButtonUp);
            
            % Outer Grid
            mainLayout = uigridlayout(obj.Figure, [3, 2]);
            mainLayout.RowHeight = {55, '1x', 40};
            mainLayout.ColumnWidth = {'1.6x', '1x'};
            mainLayout.Padding = [20 20 20 10];
            mainLayout.BackgroundColor = obj.DARK_BG;
            mainLayout.RowSpacing = 15;
            mainLayout.ColumnSpacing = 20;
            
            % --- Header ---
            headerPanel = uipanel(mainLayout, 'BackgroundColor', obj.CARD_BG, 'BorderType', 'line', 'HighlightColor', obj.BORDER);
            headerPanel.Layout.Row = 1;
            headerPanel.Layout.Column = [1 2];
            
            hl = uigridlayout(headerPanel, [1, 9]);
            hl.ColumnWidth = {40, 130, 80, 45, 90, 140, '1x', 100, 30};
            hl.Padding = [15 10 15 10];
            hl.RowHeight = {30}; % Constrain button height
            
            uilabel(hl, 'Text', 'Port:', 'FontWeight', 'bold', 'FontColor', obj.TEXT_SEC);
            obj.PortCombo = uidropdown(hl, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            
            uibutton(hl, 'Text', 'Refresh', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, ...
                'ButtonPushedFcn', @(~,~) obj.refreshPorts());
            
            uilabel(hl, 'Text', 'Baud:', 'FontWeight', 'bold', 'FontColor', obj.TEXT_SEC);
            obj.BaudCombo = uidropdown(hl, 'Items', {'9600','19200','38400','57600','115200'}, ...
                'Value', '9600', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            
            obj.ConnectBtn = uibutton(hl, 'Text', 'Connect', 'FontWeight', 'bold', ...
                'BackgroundColor', obj.SUCCESS, 'ButtonPushedFcn', @(~,~) obj.toggleConnect());
            
            uilabel(hl, 'Text', ''); % Spacer
            
            obj.CountdownLabel = uilabel(hl, 'Text', '⏱ --', 'FontName', 'Monospaced', ...
                'FontSize', 18, 'FontWeight', 'bold', 'FontColor', obj.TEXT_SEC, 'HorizontalAlignment', 'center');
            
            % --- Tabs Area (Left) ---
            obj.TabGroup = uitabgroup(mainLayout);
            obj.TabGroup.Layout.Row = 2;
            obj.TabGroup.Layout.Column = 1;
            
            obj.ManualTab = uitab(obj.TabGroup, 'Title', 'Manual Move', 'BackgroundColor', obj.PANEL_BG);
            obj.ProgramTab = uitab(obj.TabGroup, 'Title', 'Program', 'BackgroundColor', obj.PANEL_BG);
            obj.SyringeTab = uitab(obj.TabGroup, 'Title', '🧪 Syringe', 'BackgroundColor', obj.PANEL_BG);
            
            obj.setupManualTab();
            obj.setupProgramTab();
            obj.setupSyringeTab();
            
            % --- Log Area (Right) ---
            logPanel = uipanel(mainLayout, 'Title', 'Serial Log', 'BackgroundColor', obj.PANEL_BG, ...
                'ForegroundColor', obj.ACCENT, 'FontWeight', 'bold');
            logPanel.Layout.Row = 2;
            logPanel.Layout.Column = 2;
            
            ll = uigridlayout(logPanel, [2, 1]);
            ll.RowHeight = {'1x', 30};
            
            obj.LogArea = uitextarea(ll, 'Editable', 'off', 'BackgroundColor', '#0a0d12', ...
                'FontColor', '#a5f3c4', 'FontName', 'Monospaced', 'FontSize', 12);
            
            uibutton(ll, 'Text', 'Clear Log', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, ...
                'ButtonPushedFcn', @(~,~) set(obj.LogArea, 'Value', {}));
            
            % --- Status Footer ---
            statusPanel = uipanel(mainLayout, 'BackgroundColor', obj.PANEL_BG, 'BorderType', 'none');
            statusPanel.Layout.Row = 3;
            statusPanel.Layout.Column = [1 2];
            
            sl = uigridlayout(statusPanel, [1, 2]);
            obj.StatusLabel = uilabel(sl, 'Text', '⬤ Disconnected', 'FontColor', obj.DANGER);
            obj.MotorStatusLabel = uilabel(sl, 'Text', 'Motor: IDLE', 'HorizontalAlignment', 'right', 'FontColor', obj.TEXT_SEC);
        end
        
        function setupManualTab(obj)
            gl = uigridlayout(obj.ManualTab, [7, 1]);
            gl.RowHeight = {45, 45, 65, 175, 115, '1x', 55};
            gl.Padding = [15 10 15 10];
            gl.RowSpacing = 10;
            
            % Unit Toggle Row
            unitGrid = uigridlayout(gl, [1, 2]);
            unitGrid.ColumnWidth = {100, '1x'};
            unitGrid.Padding = [0 0 0 0];
            uilabel(unitGrid, 'Text', 'Input Units:', 'FontWeight', 'bold', 'FontColor', obj.TEXT_SEC, 'FontSize', 13);
            
            unitBg = uibuttongroup(unitGrid, 'BorderType', 'none', 'BackgroundColor', obj.PANEL_BG);
            unitBg.Layout.Row = 1; unitBg.Layout.Column = 2;
            obj.ManUnitStepsRb = uiradiobutton(unitBg, 'Text', 'mm', 'Value', 1, 'FontColor', obj.TEXT_PRI, 'Position', [0 12 60 22], 'FontSize', 12);
            obj.ManUnitUlRb = uiradiobutton(unitBg, 'Text', 'µL', 'Value', 0, 'FontColor', obj.TEXT_PRI, 'Enable', 'off', 'Position', [70 12 60 22], 'FontSize', 12);
            obj.ManUlBadge = uilabel(unitBg, 'Text', '(confirm syringe settings to unlock)', 'FontColor', obj.TEXT_SEC, 'FontSize', 11, 'Position', [140 12 300 22], 'FontAngle', 'italic');
            
            % Direction Group
            dirGrid = uigridlayout(gl, [1, 2]);
            dirGrid.ColumnWidth = {100, '1x'};
            dirGrid.Padding = [0 0 0 0];
            uilabel(dirGrid, 'Text', 'Direction:', 'FontWeight', 'bold', 'FontColor', obj.TEXT_SEC, 'FontSize', 13);
            
            dirBg = uibuttongroup(dirGrid, 'BorderType', 'none', 'BackgroundColor', obj.PANEL_BG);
            dirBg.Layout.Row = 1; dirBg.Layout.Column = 2;
            obj.ManDirFwdRb = uiradiobutton(dirBg, 'Text', '⬆ Forward', 'Value', 1, 'FontColor', obj.TEXT_PRI, 'Position', [0 12 110 22], 'FontSize', 12);
            obj.ManDirBwdRb = uiradiobutton(dirBg, 'Text', '⬇ Backward', 'Value', 0, 'FontColor', obj.TEXT_PRI, 'Position', [120 12 110 22], 'FontSize', 12);
            
            % Distance Panel
            distP = uipanel(gl, 'Title', 'Distance', 'BackgroundColor', obj.PANEL_BG, 'ForegroundColor', obj.ACCENT, 'FontWeight', 'bold');
            dl = uigridlayout(distP, [1, 3]);
            dl.RowHeight = {28};
            dl.ColumnWidth = {80, 40, '1x'};
            dl.Padding = [10 5 10 5];
            obj.ManDistSpin = uieditfield(dl, 'numeric', 'Value', 0.8, 'BackgroundColor', obj.CARD_BG, ...
                'FontColor', obj.TEXT_PRI, 'ValueChangedFcn', @(~,~) obj.onManualParamChanged());
            uilabel(dl, 'Text', 'mm', 'FontColor', obj.TEXT_SEC);
            obj.ManRevLabel = uilabel(dl, 'Text', '2048 steps', 'FontColor', obj.ACCENT, 'FontWeight', 'bold', 'FontSize', 16);
            
            % Speed Panel
            speedP = uipanel(gl, 'Title', 'Speed', 'BackgroundColor', obj.PANEL_BG, 'ForegroundColor', obj.ACCENT, 'FontWeight', 'bold');
            sl = uigridlayout(speedP, [5, 4]);
            sl.RowHeight = {24, 33, 33, 24, 18};
            sl.ColumnWidth = {60, '1x', 80, 50};
            sl.RowSpacing = 3;
            sl.Padding = [12 8 12 5];
            
            % Time Unit Toggle
            tul = uilabel(sl, 'Text', 'Time unit:', 'FontSize', 11, 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            tul.Layout.Row = 1; tul.Layout.Column = 1;
            
            timeBg = uibuttongroup(sl, 'BorderType', 'none', 'BackgroundColor', obj.PANEL_BG);
            timeBg.Layout.Row = 1; timeBg.Layout.Column = 2;
            obj.ManTimeS_Rb = uiradiobutton(timeBg, 'Text', '/s', 'Value', 1, 'FontColor', obj.TEXT_PRI, 'FontSize', 11, 'Position', [0 5 50 20]);
            obj.ManTimeMin_Rb = uiradiobutton(timeBg, 'Text', '/min', 'Value', 0, 'FontColor', obj.TEXT_PRI, 'FontSize', 11, 'Position', [55 5 60 20]);
            timeBg.SelectionChangedFcn = @(~,~) obj.onSpeedTimeUnitChanged();
            
            % Start Speed
            sl1 = uilabel(sl, 'Text', 'Start:', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center', 'FontSize', 12);
            sl1.Layout.Row = 2; sl1.Layout.Column = 1;
            
            obj.ManStartSlider = uislider(sl, 'Limits', [1 600], 'Value', 100, 'FontColor', obj.ACCENT, ...
                'MajorTicks', [], 'MajorTickLabels', {}, 'MinorTicks', [],...
                'ValueChangedFcn', @(s,~) obj.onSliderChanged(s, obj.ManStartSpin, 'speed'));
            obj.ManStartSlider.Layout.Row = 2; obj.ManStartSlider.Layout.Column = 2;
            
            obj.ManStartSpin = uieditfield(sl, 'numeric', 'Value', 100*obj.MM_PER_STEP, 'BackgroundColor', obj.CARD_BG, ...
                'FontColor', obj.TEXT_PRI, 'ValueChangedFcn', @(s,~) obj.onSpinChanged(s, obj.ManStartSlider, 'speed'));
            obj.ManStartSpin.Layout.Row = 2; obj.ManStartSpin.Layout.Column = 3;
            
            obj.ManStartUnit = uilabel(sl, 'Text', 'mm/s', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            obj.ManStartUnit.Layout.Row = 2; obj.ManStartUnit.Layout.Column = 4;
            
            % End Speed
            el1 = uilabel(sl, 'Text', 'End:', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center', 'FontSize', 12);
            el1.Layout.Row = 3; el1.Layout.Column = 1;
            
            obj.ManEndSlider = uislider(sl, 'Limits', [1 600], 'Value', 300, 'FontColor', obj.ACCENT, ...
                'MajorTicks', [], 'MajorTickLabels', {}, 'MinorTicks', [],...
                'ValueChangedFcn', @(s,~) obj.onSliderChanged(s, obj.ManEndSpin, 'speed'));
            obj.ManEndSlider.Layout.Row = 3; obj.ManEndSlider.Layout.Column = 2;
            
            obj.ManEndSpin = uieditfield(sl, 'numeric', 'Value', 300*obj.MM_PER_STEP, 'BackgroundColor', obj.CARD_BG, ...
                'FontColor', obj.TEXT_PRI, 'ValueChangedFcn', @(s,~) obj.onSpinChanged(s, obj.ManEndSlider, 'speed'));
            obj.ManEndSpin.Layout.Row = 3; obj.ManEndSpin.Layout.Column = 3;
            
            obj.ManEndUnit = uilabel(sl, 'Text', 'mm/s', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            obj.ManEndUnit.Layout.Row = 3; obj.ManEndUnit.Layout.Column = 4;
            
            % Duration Row
            dl1 = uilabel(sl, 'Text', 'Duration (est.):', 'FontColor', obj.TEXT_SEC, 'FontSize', 12, 'VerticalAlignment', 'center');
            dl1.Layout.Row = 4; dl1.Layout.Column = 1;
            obj.ManDurationLabel = uilabel(sl, 'Text', '---', 'FontColor', obj.ACCENT, 'FontWeight', 'bold', 'FontSize', 12, 'VerticalAlignment', 'center');
            obj.ManDurationLabel.Layout.Row = 4; obj.ManDurationLabel.Layout.Column = [2 4];
            
            % Range Hint
            obj.ManRangeHintSpeed = uilabel(sl, 'Text', sprintf('Range: %.5f – %.4f mm/s  (1 – 600 steps/s)', obj.MM_PER_STEP, 600*obj.MM_PER_STEP), ...
                'FontSize', 11, 'FontColor', obj.TEXT_SEC, 'FontAngle', 'italic');
            obj.ManRangeHintSpeed.Layout.Row = 5; obj.ManRangeHintSpeed.Layout.Column = [1 4];
            
            % Accel Panel
            accelP = uipanel(gl, 'Title', 'Acceleration', 'BackgroundColor', obj.PANEL_BG, 'ForegroundColor', obj.ACCENT, 'FontWeight', 'bold');
            al = uigridlayout(accelP, [3, 4]);
            al.RowHeight = {24, 33, 18};
            al.ColumnWidth = {60, '1x', 80, 50};
            al.RowSpacing = 3;
            al.Padding = [12 8 12 5];
            
            % Time Unit Toggle
            alul = uilabel(al, 'Text', 'Time unit:', 'FontSize', 11, 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            alul.Layout.Row = 1; alul.Layout.Column = 1;
            
            accTimeBg = uibuttongroup(al, 'BorderType', 'none', 'BackgroundColor', obj.PANEL_BG);
            accTimeBg.Layout.Row = 1; accTimeBg.Layout.Column = 2;
            obj.ManAccelS_Rb = uiradiobutton(accTimeBg, 'Text', '/s²', 'Value', 1, 'FontColor', obj.TEXT_PRI, 'FontSize', 11, 'Position', [0 5 50 20]);
            obj.ManAccelMin_Rb = uiradiobutton(accTimeBg, 'Text', '/min²', 'Value', 0, 'FontColor', obj.TEXT_PRI, 'FontSize', 11, 'Position', [55 5 70 20]);
            accTimeBg.SelectionChangedFcn = @(~,~) obj.onAccelTimeUnitChanged();
            
            % Accel Slider Row
            alv = uilabel(al, 'Text', 'Value:', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center', 'FontSize', 12);
            alv.Layout.Row = 2; alv.Layout.Column = 1;
            
            obj.ManAccelSlider = uislider(al, 'Limits', [0 400], 'Value', 100, 'FontColor', obj.ACCENT, ...
                'MajorTicks', [], 'MajorTickLabels', {}, 'MinorTicks', [],...
                'ValueChangedFcn', @(s,~) obj.onSliderChanged(s, obj.ManAccelSpin, 'accel'));
            obj.ManAccelSlider.Layout.Row = 2; obj.ManAccelSlider.Layout.Column = 2;
            
            obj.ManAccelSpin = uieditfield(al, 'numeric', 'Value', 100*obj.MM_PER_STEP, 'BackgroundColor', obj.CARD_BG, ...
                'FontColor', obj.TEXT_PRI, 'ValueChangedFcn', @(s,~) obj.onSpinChanged(s, obj.ManAccelSlider, 'accel'));
            obj.ManAccelSpin.Layout.Row = 2; obj.ManAccelSpin.Layout.Column = 3;
            
            obj.ManAccelUnit = uilabel(al, 'Text', 'mm/s²', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            obj.ManAccelUnit.Layout.Row = 2; obj.ManAccelUnit.Layout.Column = 4;
            
            % Accel Hint
            hintStr = sprintf('Range: ±%.4f mm/s²  (0 = constant speed, max ±400 steps/s²)', 400 * obj.MM_PER_STEP);
            al_hint = uilabel(al, 'Text', hintStr, 'FontSize', 11, 'FontColor', obj.TEXT_SEC, 'FontAngle', 'italic', 'VerticalAlignment', 'top');
            al_hint.Layout.Row = 3; al_hint.Layout.Column = [1 4];
            
            % Continuous Jog Panel
            jogP = uipanel(gl, 'Title', 'Continuous Jog', 'BackgroundColor', obj.PANEL_BG, 'ForegroundColor', obj.ACCENT, 'FontWeight', 'bold');
            jl = uigridlayout(jogP, [2, 1]);
            jl.RowHeight = {'1x', '2x'};
            jl.RowSpacing = 10;
            jl.Padding = [12 10 12 10];

            % Speed row
            jogSpdRow = uigridlayout(jl, [1, 4]);
            jogSpdRow.ColumnWidth = {50, 100, 50, '1x'};
            jogSpdRow.Padding = [0 0 0 0];
            uilabel(jogSpdRow, 'Text', 'Speed:', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center', 'FontSize', 12);
            obj.ManJogSpeedSpin = uieditfield(jogSpdRow, 'numeric', 'Value', 100*obj.MM_PER_STEP, ...
                'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            uilabel(jogSpdRow, 'Text', 'mm/s', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            uilabel(jogSpdRow, 'Text', ''); % spacer

            % Button row
            jogBtnRow = uigridlayout(jl, [1, 2]);
            jogBtnRow.Padding = [0 0 0 0];
            obj.ManJogFwdBtn = uibutton(jogBtnRow, 'Text', '⬆  Jog Forward', 'FontSize', 13, 'FontWeight', 'bold', ...
                'BackgroundColor', obj.ACCENT);
            obj.ManJogBwdBtn = uibutton(jogBtnRow, 'Text', '⬇  Jog Backward', 'FontSize', 13, 'FontWeight', 'bold', ...
                'BackgroundColor', obj.ACCENT);

            % Actions
            actGrid = uigridlayout(gl, [1, 2]);
            actGrid.ColumnWidth = {'3x', '1x'};
            obj.ManMoveBtn = uibutton(actGrid, 'Text', '▶  Move Motor', 'FontSize', 13, 'FontWeight', 'bold', ...
                'BackgroundColor', obj.ACCENT, 'ButtonPushedFcn', @(~,~) obj.doManualMove());
            obj.ManStopBtn = uibutton(actGrid, 'Text', '🛑  STOP', 'FontSize', 13, 'FontWeight', 'bold', ...
                'BackgroundColor', obj.DANGER, 'FontColor', 'white', 'ButtonPushedFcn', @(~,~) obj.doAbort());
        end
        
        function setupProgramTab(obj)
            gl = uigridlayout(obj.ProgramTab, [4, 1]);
            gl.RowHeight = {'1x', 50, 70, 30};
            gl.Padding = [20 20 20 10];
            gl.RowSpacing = 15;
            
            obj.ProgTable = uitable(gl, 'ColumnName', {'#', 'Direction', 'Distance (steps)', 'Start Spd', 'End Spd', 'Accel'}, ...
                'BackgroundColor', obj.CARD_BG, 'SelectionType', 'row');
            % Style for dark theme
            s = uistyle('FontColor', obj.TEXT_PRI, 'BackgroundColor', obj.CARD_BG);
            addStyle(obj.ProgTable, s);
            
            btns = uigridlayout(gl, [1, 4]);
            btns.ColumnSpacing = 10;
            obj.ProgAddBtn = uibutton(btns, 'Text', '➕ Add Step', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, 'FontWeight', 'bold');
            obj.ProgAddBtn.ButtonPushedFcn = @(~,~) obj.addStepDialog();
            obj.ProgDelBtn = uibutton(btns, 'Text', '🗑 Delete Step', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, 'FontWeight', 'bold');
            obj.ProgDelBtn.ButtonPushedFcn = @(~,~) obj.deleteStep();
            obj.ProgClearBtn = uibutton(btns, 'Text', '✖ Clear All', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, 'FontWeight', 'bold');
            obj.ProgClearBtn.ButtonPushedFcn = @(~,~) obj.clearProgram();
            
            runGrid = uigridlayout(gl, [1, 2]);
            runGrid.ColumnWidth = {'3x', '1x'};
            runGrid.ColumnSpacing = 15;
            obj.ProgRunBtn = uibutton(runGrid, 'Text', '▶▶  Run Program Sequence', 'FontSize', 16, 'FontWeight', 'bold', ...
                'BackgroundColor', obj.SUCCESS, 'ButtonPushedFcn', @(~,~) obj.runProgram());
            obj.ProgStopBtn = uibutton(runGrid, 'Text', '🛑  STOP', 'FontSize', 16, 'FontWeight', 'bold', ...
                'BackgroundColor', obj.DANGER, 'FontColor', 'white', 'ButtonPushedFcn', @(~,~) obj.doAbort());
                
            obj.ProgDurationLabel = uilabel(gl, 'Text', 'Total Program Duration: ---', 'HorizontalAlignment', 'center', ...
                'FontColor', obj.ACCENT, 'FontWeight', 'bold', 'FontSize', 14);
        end
        
        function setupSyringeTab(obj)
            gl = uigridlayout(obj.SyringeTab, [3, 1]);
            gl.RowHeight = {200, 140, 110};
            gl.Padding = [20 20 20 20];
            gl.RowSpacing = 15;
            
            % Setup
            setupP = uipanel(gl, 'Title', 'Syringe Geometry Calibration', 'BackgroundColor', obj.PANEL_BG, 'ForegroundColor', obj.ACCENT, 'FontWeight', 'bold');
            fl = uigridlayout(setupP, [6, 2]);
            fl.ColumnWidth = {160, '1x'};
            fl.RowSpacing = 8;
            
            % Preset picker
            uilabel(fl, 'Text', 'Syringe preset:', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            presetLabels = obj.HAMILTON_1700_PRESETS(:,1);
            obj.SyrPresetCombo = uidropdown(fl, 'Items', presetLabels', ...
                'Value', 'Custom…', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, ...
                'Tooltip', 'Select a Hamilton 1700 syringe to auto-fill volume and stroke.');
            obj.SyrPresetCombo.ValueChangedFcn = @(~,e) obj.onSyringePresetChanged(e.Value);
            
            uilabel(fl, 'Text', 'Total Syringe Volume:', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            ug = uigridlayout(fl, [1, 2]);
            ug.Padding = [0 0 0 0];
            ug.ColumnWidth = {80, '1x'};
            obj.SyrVolSpin = uieditfield(ug, 'numeric', 'Value', 50, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, ...
                'ValueChangedFcn', @(~,~) obj.resetPresetToCustom());
            obj.SyrUnitCombo = uidropdown(ug, 'Items', {'nL','µL','mL'}, 'Value', 'µL', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            
            uilabel(fl, 'Text', 'Full Plunger Stroke (mm):', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            sg = uigridlayout(fl, [1, 1]);
            sg.Padding = [0 0 0 0];
            sg.ColumnWidth = {80};
            obj.SyrStrokeSpin = uieditfield(sg, 'numeric', 'Value', 60, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, ...
                'ValueChangedFcn', @(~,~) obj.resetPresetToCustom());
            
            uilabel(fl, 'Text', 'Calculated µL / Step:', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            obj.SyrUlStepLabel = uilabel(fl, 'Text', '-', 'FontColor', obj.ACCENT, 'FontWeight', 'bold', 'FontSize', 13);
            
            uilabel(fl, 'Text', 'Calculated Steps / µL:', 'FontColor', obj.TEXT_SEC, 'VerticalAlignment', 'center');
            obj.SyrStepUlLabel = uilabel(fl, 'Text', '-', 'FontColor', obj.ACCENT, 'FontWeight', 'bold', 'FontSize', 13);
            
            obj.SyrConfirmChk = uicheckbox(fl, 'Text', 'Confirm Settings — unlock µL input mode', 'FontColor', obj.TEXT_PRI, 'FontWeight', 'bold');
            obj.SyrConfirmChk.Layout.Column = [1 2];
            obj.SyrConfirmChk.ValueChangedFcn = @(~,~) obj.onSyringeConfirmed();
            
            % Converters
            conv1P = uipanel(gl, 'Title', 'Quick Converter: Volume → Steps', 'BackgroundColor', obj.PANEL_BG, 'ForegroundColor', obj.ACCENT, 'FontWeight', 'bold');
            c1l = uigridlayout(conv1P, [1, 3]);
            c1l.RowHeight = {30};
            c1l.ColumnWidth = {80, 40, '1x'};
            obj.ConvInputUlSpin = uieditfield(c1l, 'numeric', 'Value', 1, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            uilabel(c1l, 'Text', '➡', 'FontSize', 22, 'FontColor', obj.ACCENT, 'HorizontalAlignment', 'center');
            obj.ConvUlToStepsLabel = uilabel(c1l, 'Text', '--- steps', 'FontColor', obj.ACCENT, 'FontSize', 16, 'FontWeight', 'bold');
            
            conv2P = uipanel(gl, 'Title', 'Quick Converter: Travel → Volume', 'BackgroundColor', obj.PANEL_BG, 'ForegroundColor', obj.ACCENT, 'FontWeight', 'bold');
            c2l = uigridlayout(conv2P, [1, 3]);
            c2l.RowHeight = {30};
            c2l.ColumnWidth = {80, 40, '1x'};
            obj.ConvInputMmSpin = uieditfield(c2l, 'numeric', 'Value', 0.8, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            uilabel(c2l, 'Text', '➡', 'FontSize', 22, 'FontColor', obj.ACCENT, 'HorizontalAlignment', 'center');
            obj.ConvMmToUlLabel = uilabel(c2l, 'Text', '--- µL', 'FontColor', obj.ACCENT, 'FontSize', 16, 'FontWeight', 'bold');
            
            % Wire updates
            obj.SyrVolSpin.ValueChangedFcn = @(~,~) obj.resetPresetToCustom();
            obj.SyrStrokeSpin.ValueChangedFcn = @(~,~) obj.resetPresetToCustom();
            obj.ConvInputUlSpin.ValueChangedFcn = @(~,~) obj.updateSyringeCalcs();
            obj.ConvInputMmSpin.ValueChangedFcn = @(~,~) obj.updateSyringeCalcs();
            obj.updateSyringeCalcs();
        end
        
        % --- Core Logic ---
        function refreshPorts(obj)
            ports = serialportlist("available");
            if isempty(ports), obj.PortCombo.Items = {'No ports found'}; else, obj.PortCombo.Items = cellstr(ports); end
        end
        
        function toggleConnect(obj)
            if strcmp(obj.ConnectBtn.Text, 'Connect')
                try
                    obj.SerialObj = serialport(obj.PortCombo.Value, str2double(obj.BaudCombo.Value));
                    configureTerminator(obj.SerialObj, "LF");
                    configureCallback(obj.SerialObj, "terminator", @obj.onLineReceived);
                    obj.ConnectBtn.Text = 'Disconnect';
                    obj.ConnectBtn.BackgroundColor = obj.DANGER;
                    obj.StatusLabel.Text = ['⬤ ' char(obj.PortCombo.Value)];
                    obj.StatusLabel.FontColor = obj.SUCCESS;
                    obj.logLine(sprintf("[Connected to %s]", obj.PortCombo.Value));
                catch e, uialert(obj.Figure, e.message, 'Serial Error'); end
            else
                delete(obj.SerialObj); obj.SerialObj = [];
                obj.ConnectBtn.Text = 'Connect'; obj.ConnectBtn.BackgroundColor = obj.SUCCESS;
                obj.StatusLabel.Text = '⬤ Disconnected'; obj.StatusLabel.FontColor = obj.DANGER;
                obj.logLine("[Disconnected]");
            end
        end
        
        function onLineReceived(obj, src, ~)
            line = readline(src);
            if isempty(line), return; end
            if obj.isLoggable(line), obj.logLine(line); end
            obj.parseArduinoLine(line);
        end

        function result = isLoggable(~, line)
            s = strtrim(line);
            u = upper(s);
            result = startsWith(u, '[DONE]') || ...     % [DONE] Move/Program complete.
                     startsWith(u, '[ABORTED]') || ...  % [ABORTED] Motor stopped.
                     startsWith(u, '[STEP') || ...      % [STEP N/M] Starting...
                     startsWith(u, 'STARTING') || ...   % Starting move… / Starting jog…
                     startsWith(s, '!') || ...          % firmware errors/warnings
                     strcmp(s, 'Step added.') || ...
                     strcmp(s, 'Step deleted.') || ...
                     strcmp(s, 'Program cleared.');
        end
        
        function parseArduinoLine(obj, line)
            upperL = upper(strtrim(line));
            
            % State Monitoring
            if contains(upperL, "STARTING MOVE") || contains(upperL, "STARTING...") || contains(upperL, "STARTING JOG")
                obj.setMotorState('MOVING');
            elseif contains(upperL, "[DONE]") || contains(upperL, "[ABORTED]")
                obj.setMotorState('IDLE');
            end
            
            % Prompt Protocol
            if contains(line, ">")
                if ~isempty(obj.ManualStepPending)
                    st = obj.ManualStepPending;
                    if contains(upperL, "DIRECTION"), obj.sendRaw(st.dir);
                    elseif contains(upperL, "DISTANCE"), obj.sendRaw(num2str(st.distance));
                    elseif contains(upperL, "START SPD"), obj.sendRaw(num2str(st.start_speed));
                    elseif contains(upperL, "END SPD"), obj.sendRaw(num2str(st.end_speed));
                    elseif contains(upperL, "ACCEL"), obj.sendRaw(num2str(st.accel)); obj.ManualStepPending = []; end
                elseif ~isempty(obj.ProgStepPending)
                    st = obj.ProgStepPending;
                    if contains(upperL, "DIRECTION"), obj.sendRaw(st.dir);
                    elseif contains(upperL, "DISTANCE"), obj.sendRaw(num2str(st.distance));
                    elseif contains(upperL, "START SPD"), obj.sendRaw(num2str(st.start_speed));
                    elseif contains(upperL, "END SPD"), obj.sendRaw(num2str(st.end_speed));
                    elseif contains(upperL, "ACCEL"), obj.sendRaw(num2str(st.accel)); obj.ProgStepPending = []; obj.CmdQueue = [obj.CmdQueue, {'Q'}]; end
                elseif ~isempty(obj.CmdQueue)
                    cmd = obj.CmdQueue{1}; obj.CmdQueue(1) = []; obj.sendRaw(cmd);
                end
            end
            
            % Sync Table
            if contains(upperL, "DIR") && contains(upperL, "DIST"), obj.Program = struct('forward', {}, 'distance', {}, 'start_speed', {}, 'end_speed', {}, 'accel', {}); end
            parts = strsplit(strtrim(line));
            if numel(parts) >= 6 && ~isnan(str2double(parts{1}))
                obj.addProgramRow(parts);
            end
        end
        
        function setMotorState(obj, state)
            obj.MotorState = state;
            if strcmp(state, 'MOVING')
                obj.MotorStatusLabel.Text = 'Motor: RUNNING  ●'; obj.MotorStatusLabel.FontColor = obj.SUCCESS;
            else
                obj.MotorStatusLabel.Text = 'Motor: IDLE'; obj.MotorStatusLabel.FontColor = obj.TEXT_SEC;
                obj.stopCountdown();
            end
        end
        
        % --- Interaction Handlers ---
        function onSliderChanged(obj, src, spin, type)
            if obj.SyncingSpeed, return; end
            obj.SyncingSpeed = true;
            scale = 1.0;
            if strcmp(type, 'speed') && obj.ManTimeMin_Rb.Value, scale = 60.0; end
            if strcmp(type, 'accel') && obj.ManAccelMin_Rb.Value, scale = 3600.0; end
            
            spin.Value = round(src.Value * obj.MM_PER_STEP * scale, 4);
            obj.SyncingSpeed = false;
            obj.onManualParamChanged();
        end
        
        function onSpinChanged(obj, src, slider, type)
            if obj.SyncingSpeed, return; end
            obj.SyncingSpeed = true;
            scale = 1.0;
            if strcmp(type, 'speed') && obj.ManTimeMin_Rb.Value, scale = 60.0; end
            if strcmp(type, 'accel') && obj.ManAccelMin_Rb.Value, scale = 3600.0; end
            
            slider.Value = max(slider.Limits(1), min(slider.Limits(2), round((src.Value / scale) / obj.MM_PER_STEP)));
            obj.SyncingSpeed = false;
            obj.onManualParamChanged();
        end
        
        function onSpeedTimeUnitChanged(obj)
            unit = 'mm/s'; scale = 1.0;
            if obj.ManTimeMin_Rb.Value, unit = 'mm/min'; scale = 60.0; end
            obj.ManStartUnit.Text = unit; obj.ManEndUnit.Text = unit;
            
            % Update displays without triggering slider jumps
            obj.SyncingSpeed = true;
            obj.ManStartSpin.Value = round(obj.ManStartSlider.Value * obj.MM_PER_STEP * scale, 4);
            obj.ManEndSpin.Value = round(obj.ManEndSlider.Value * obj.MM_PER_STEP * scale, 4);
            obj.SyncingSpeed = false;
        end
        
        function onAccelTimeUnitChanged(obj)
            unit = 'mm/s²'; scale = 1.0;
            if obj.ManAccelMin_Rb.Value, unit = 'mm/min²'; scale = 3600.0; end
            obj.ManAccelUnit.Text = unit;
            
            obj.SyncingSpeed = true;
            obj.ManAccelSpin.Value = round(obj.ManAccelSlider.Value * obj.MM_PER_STEP * scale, 4);
            obj.SyncingSpeed = false;
        end
        
        function onManualParamChanged(obj)
            dist_steps = round(obj.ManDistSpin.Value / obj.MM_PER_STEP);
            obj.ManRevLabel.Text = sprintf('%d steps', dist_steps);
            
            % Update Duration
            st = struct('distance', dist_steps, 'start_speed', obj.ManStartSlider.Value, ...
                'end_speed', obj.ManEndSlider.Value, 'accel', obj.ManAccelSlider.Value);
            dur = obj.calculateDuration(st);
            obj.ManDurationLabel.Text = sprintf('Duration (est.): %.2f s', dur);
        end
        
        function dur = calculateDuration(~, st)
            d = double(st.distance); v0 = double(st.start_speed); v1 = double(st.end_speed); a = double(st.accel);
            if v0 <= 0 || d <= 0, dur = 0; return; end
            if a == 0 || v0 == v1, dur = d/v0; return; end
            x_ramp = (v1^2 - v0^2)/(2*a);
            if x_ramp >= d || x_ramp <= 0, dur = abs(sqrt(max(0, v0^2 + 2*a*d)) - v0)/abs(a);
            else, dur = abs(v1-v0)/abs(a) + (d - x_ramp)/v1; end
        end
        
        function doManualMove(obj)
            st = struct();
            st.dir = 'F'; if obj.ManDirBwdRb.Value, st.dir = 'B'; end
            st.distance = round(obj.ManDistSpin.Value / obj.MM_PER_STEP);
            st.start_speed = obj.ManStartSlider.Value;
            st.end_speed = obj.ManEndSlider.Value;
            st.accel = obj.ManAccelSlider.Value;
            obj.ManualStepPending = st;
            obj.startCountdown(obj.calculateDuration(st));
            obj.sendRaw('M');
        end
        
        function doAbort(obj)
            obj.sendRaw('X'); obj.stopCountdown();
        end

        function doJog(obj, forward)
            if obj.JogActive, return; end
            obj.JogActive = true;
            speed_steps = max(1, min(600, round(obj.ManJogSpeedSpin.Value / obj.MM_PER_STEP)));
            if forward
                dir = 'F';
            else
                dir = 'B';
            end
            obj.sendRaw(sprintf('K %s %d', dir, speed_steps));
        end

        function doJogStop(obj)
            if ~obj.JogActive, return; end
            obj.JogActive = false;
            obj.sendRaw('X');
        end

        function onWindowButtonDown(obj, ~, ~)
            co = obj.Figure.CurrentObject;
            if isequal(co, obj.ManJogFwdBtn)
                obj.doJog(true);
            elseif isequal(co, obj.ManJogBwdBtn)
                obj.doJog(false);
            end
        end

        function onWindowButtonUp(obj, ~, ~)
            obj.doJogStop();
        end
        
        function addStepDialog(obj)
            if size(obj.ProgTable.Data, 1) >= 5, uialert(obj.Figure, 'Program full (max 5 steps).', 'Info'); return; end
            
            % Create Modal Dialog
            pos = obj.Figure.Position;
            d = uifigure('Name', 'Add Program Step', 'Position', [pos(1)+100 pos(2)+100 380 460], 'Color', obj.DARK_BG, 'WindowStyle', 'modal');
            gl_d = uigridlayout(d, [7, 1]);
            gl_d.RowHeight = {40, 65, 35, 35, 35, 35, 60};
            gl_d.Padding = [25 25 25 20];
            gl_d.RowSpacing = 10;
            
            uilabel(gl_d, 'Text', 'CONFIGURE NEW STEP', 'FontWeight', 'bold', 'FontColor', obj.ACCENT, 'FontSize', 16, 'HorizontalAlignment', 'center');
            
            % Direction
            dirG = uigridlayout(gl_d, [1, 2]);
            dirG.ColumnWidth = {110, '1x'};
            uilabel(dirG, 'Text', 'Direction:', 'FontColor', obj.TEXT_SEC, 'FontWeight', 'bold');
            
            dirBg_d = uibuttongroup(dirG, 'BorderType', 'none', 'BackgroundColor', obj.DARK_BG);
            dirBg_d.Layout.Row = 1; dirBg_d.Layout.Column = 2;
            fwdRb = uiradiobutton(dirBg_d, 'Text', 'Forward', 'Value', 1, 'FontColor', obj.TEXT_PRI, 'Position', [0 22 90 22]);
            bwdRb = uiradiobutton(dirBg_d, 'Text', 'Backward', 'Value', 0, 'FontColor', obj.TEXT_PRI, 'Position', [100 22 100 22]);
            
            % Distance
            distG = uigridlayout(gl_d, [1, 2]);
            distG.ColumnWidth = {110, 80};
            uilabel(distG, 'Text', 'Distance (mm):', 'FontColor', obj.TEXT_SEC, 'FontWeight', 'bold');
            distE = uieditfield(distG, 'numeric', 'Value', 0.8, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            
            % Speeds
            sSpdG = uigridlayout(gl_d, [1, 2]);
            sSpdG.ColumnWidth = {110, 80};
            uilabel(sSpdG, 'Text', 'Start Spd (s/s):', 'FontColor', obj.TEXT_SEC, 'FontWeight', 'bold');
            sSpdE = uieditfield(sSpdG, 'numeric', 'Value', 100, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            
            eSpdG = uigridlayout(gl_d, [1, 2]);
            eSpdG.ColumnWidth = {110, 80};
            uilabel(eSpdG, 'Text', 'End Spd (s/s):', 'FontColor', obj.TEXT_SEC, 'FontWeight', 'bold');
            eSpdE = uieditfield(eSpdG, 'numeric', 'Value', 300, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            
            % Accel
            accG = uigridlayout(gl_d, [1, 2]);
            accG.ColumnWidth = {110, 80};
            uilabel(accG, 'Text', 'Accel (s/s²):', 'FontColor', obj.TEXT_SEC, 'FontWeight', 'bold');
            accE = uieditfield(accG, 'numeric', 'Value', 100, 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI);
            
            % Buttons
            btnG = uigridlayout(gl_d, [1, 2]);
            btnG.ColumnSpacing = 15;
            uibutton(btnG, 'Text', 'Confirm', 'FontWeight', 'bold', 'BackgroundColor', obj.SUCCESS, 'ButtonPushedFcn', @(~,~) obj.confirmAddStep(d, fwdRb, distE, sSpdE, eSpdE, accE));
            uibutton(btnG, 'Text', 'Cancel', 'FontWeight', 'bold', 'BackgroundColor', obj.CARD_BG, 'FontColor', obj.TEXT_PRI, 'ButtonPushedFcn', @(~,~) delete(d));
        end
        
        function confirmAddStep(obj, d, fwdRb, distE, sSpdE, eSpdE, accE)
            st = struct();
            st.dir = 'F'; if ~fwdRb.Value, st.dir = 'B'; end
            st.distance = round(distE.Value / obj.MM_PER_STEP);
            st.start_speed = sSpdE.Value;
            st.end_speed = eSpdE.Value;
            st.accel = accE.Value;
            
            obj.ProgStepPending = st;
            delete(d);
            
            % Execute Serial commands
            obj.sendRaw('P');
            obj.CmdQueue = [obj.CmdQueue, {'A'}];
        end
        
        function deleteStep(obj)
            sel = obj.ProgTable.Selection;
            if isempty(sel), uialert(obj.Figure, 'Select a step to delete.', 'Info'); return; end
            obj.sendRaw('P');
            obj.CmdQueue = [obj.CmdQueue, {sprintf('D %d', sel(1))}];
        end
        
        function clearProgram(obj)
            obj.sendRaw('C');
        end
        
        function runProgram(obj)
            if isempty(obj.ProgTable.Data), return; end
            total_dur = 0;
            data = obj.ProgTable.Data;
            for i = 1:size(data, 1)
                st = struct('distance', data{i,3}, 'start_speed', data{i,4}, 'end_speed', data{i,5}, 'accel', data{i,6});
                total_dur = total_dur + obj.calculateDuration(st);
            end
            obj.startCountdown(total_dur);
            obj.sendRaw('R');
        end
        
        function updateSyringeCalcs(obj)
            vol = obj.SyrVolSpin.Value; stroke = obj.SyrStrokeSpin.Value;
            if stroke <= 0 || vol <= 0, return; end
            ul_per_step = (vol / stroke) * obj.MM_PER_STEP;
            obj.SyrUlStepLabel.Text = sprintf('%.6f µL/step', ul_per_step);
            obj.SyrStepUlLabel.Text = sprintf('%.2f steps/µL', 1/ul_per_step);
            
            % Converters
            obj.ConvUlToStepsLabel.Text = sprintf('%.0f steps', obj.ConvInputUlSpin.Value / ul_per_step);
            obj.ConvMmToUlLabel.Text = sprintf('%.4f %s', (obj.ConvInputMmSpin.Value / obj.MM_PER_STEP) * ul_per_step, obj.SyrUnitCombo.Value);
        end
        
        function onSyringePresetChanged(obj, label)
            % Find the selected preset row
            presets = obj.HAMILTON_1700_PRESETS;
            row = find(strcmp(presets(:,1), label));
            if isempty(row) || isempty(presets{row,2})
                return  % "Custom…" selected — do nothing
            end
            vol_ul   = presets{row, 2};
            stroke   = presets{row, 3};
            obj.ApplyingPreset = true;
            try
                obj.SyrUnitCombo.Value = 'µL';
                obj.SyrVolSpin.Value   = vol_ul;
                obj.SyrStrokeSpin.Value = stroke;
            catch
            end
            obj.ApplyingPreset = false;
            obj.updateSyringeCalcs();
        end
        
        function resetPresetToCustom(obj)
            % Reset preset dropdown to "Custom…" when the user edits fields.
            if obj.ApplyingPreset, return; end
            if ~strcmp(obj.SyrPresetCombo.Value, 'Custom…')
                obj.SyrPresetCombo.Value = 'Custom…';
            end
            obj.updateSyringeCalcs();
        end
        
        function onSyringeConfirmed(obj)
            if obj.SyrConfirmChk.Value
                obj.ManUnitUlRb.Enable = 'on';
                obj.ManUlBadge.Text = '🧪 µL input mode active'; obj.ManUlBadge.FontColor = obj.ACCENT;
            else
                obj.ManUnitUlRb.Enable = 'off'; obj.ManUnitStepsRb.Value = 1;
                obj.ManUlBadge.Text = '(confirm syringe settings to unlock)'; obj.ManUlBadge.FontColor = obj.TEXT_SEC;
            end
        end
        
        % --- Utilities ---
        function logLine(obj, text)
            obj.LogArea.Value = [obj.LogArea.Value; {char(text)}];
            drawnow;
        end
        
        function sendRaw(obj, text)
            if ~isempty(obj.SerialObj) && isvalid(obj.SerialObj), writeline(obj.SerialObj, text); end
        end
        
        function onGlobalKey(obj, ~, event)
            if strcmp(event.Key, 'escape')
                obj.doAbort();
            elseif strcmp(event.Key, 'uparrow')
                obj.doJog(true);
            elseif strcmp(event.Key, 'downarrow')
                obj.doJog(false);
            end
        end

        function onGlobalKeyRelease(obj, ~, event)
            if strcmp(event.Key, 'uparrow') || strcmp(event.Key, 'downarrow')
                obj.doJogStop();
            end
        end
        
        function startCountdown(obj, dur)
            obj.CountdownValue = dur;
            obj.CountdownLabel.FontColor = obj.ACCENT;
            start(obj.CountdownTimer);
        end
        
        function stopCountdown(obj)
            stop(obj.CountdownTimer);
            obj.CountdownLabel.Text = '⏱ --';
            obj.CountdownLabel.FontColor = obj.TEXT_SEC;
        end
        
        function onCountdownTick(obj)
            obj.CountdownValue = max(0, obj.CountdownValue - 0.1);
            obj.CountdownLabel.Text = sprintf('⏱ %.1fs', obj.CountdownValue);
            if obj.CountdownValue <= 0, stop(obj.CountdownTimer); end
        end
        
        function addProgramRow(obj, parts)
             idx = str2double(parts{1});
             dir = parts{2};
             dist = str2double(parts{3});
             s_spd = str2double(parts{4});
             e_spd = str2double(parts{5});
             acc = str2double(parts{6});
             
             row = {idx, dir, dist, s_spd, e_spd, acc};
             obj.ProgTable.Data(idx, :) = row;
        end
    end
end
