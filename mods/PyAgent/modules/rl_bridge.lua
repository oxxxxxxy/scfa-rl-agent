-- PyAgent Autonomous Mission & IPC Bridge for Supreme Commander: Forged Alliance
-- Faction-aware, robust zero-dependency in-engine coordinator

local ScenarioUtils = import('/lua/sim/ScenarioUtilities.lua')

_G.PyAgent_Bridge = {
    Running = false,
    StepId = 0,
    ArmyIndex = 1,
    GameSpeed = 0,
    DisableAI = true,
    TickInterval = 10,
    CMD_PATH = '/mods/pyagent/_pyagent_cmd.lua',
    LastCmdSeq = 0,
}

-- Blueprint mapping per faction
local FACTION_BLUEPRINTS = {
    -- Cybran
    [3] = {
        factory = 'urb0101',
        mex = 'urb1103',
        pgen = 'urb1101',
        engineer = 'url0105',
        pd = 'urb2101',
        aa = 'urb2104',
        wall = 'urb5101'
    },
    -- UEF
    [1] = {
        factory = 'ueb0101',
        mex = 'ueb1103',
        pgen = 'ueb1101',
        engineer = 'uel0105',
        pd = 'ueb2101',
        aa = 'ueb2104',
        wall = 'ueb5101'
    },
    -- Aeon
    [2] = {
        factory = 'uab0101',
        mex = 'uab1103',
        pgen = 'uab1101',
        engineer = 'ual0105',
        pd = 'uab2101',
        aa = 'uab2104',
        wall = 'uab5101'
    },
    -- Seraphim
    [4] = {
        factory = 'xsb0101',
        mex = 'xsb1103',
        pgen = 'xsb1101',
        engineer = 'xsl0105',
        pd = 'xsb2101',
        aa = 'xsb2104',
        wall = 'xsb5101'
    }
}

-- ============================================================
-- Fast JSON Serializer for Game State Logging
-- ============================================================
local function SerializeJson(val)
    local t = type(val)
    if t == 'number' then
        if val ~= val then return "0" end
        if val > 999999999 then return "999999" end
        if val < -999999999 then return "-999999" end
        return string.format("%.2f", val)
    elseif t == 'string' then
        local s = val
        s = string.gsub(s, '\\', '\\\\')
        s = string.gsub(s, '"', '\\"')
        s = string.gsub(s, '\n', '\\n')
        s = string.gsub(s, '\r', '\\r')
        return '"' .. s .. '"'
    elseif t == 'boolean' then
        return val and "true" or "false"
    elseif t == 'table' then
        local isArray = true
        local n = 0
        for k, v in pairs(val) do
            n = n + 1
            if type(k) ~= 'number' or k ~= n then
                isArray = false
                break
            end
        end
        local parts = {}
        if isArray then
            for i, v in ipairs(val) do
                table.insert(parts, SerializeJson(v))
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            for k, v in pairs(val) do
                table.insert(parts, '"' .. tostring(k) .. '":' .. SerializeJson(v))
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    else
        return "null"
    end
end

-- ============================================================
-- Category tags helper
-- ============================================================
local function GetUnitTags(unit)
    local tags = {}
    if EntityCategoryContains(categories.COMMAND, unit) then table.insert(tags, "COMMANDER") end
    if EntityCategoryContains(categories.SUBCOMMANDER, unit) then table.insert(tags, "SUBCOMMANDER") end
    if EntityCategoryContains(categories.ENGINEER, unit) then table.insert(tags, "ENGINEER") end
    if EntityCategoryContains(categories.FACTORY, unit) then table.insert(tags, "FACTORY") end
    if EntityCategoryContains(categories.LAND, unit) then table.insert(tags, "LAND") end
    if EntityCategoryContains(categories.AIR, unit) then table.insert(tags, "AIR") end
    if EntityCategoryContains(categories.NAVAL, unit) then table.insert(tags, "NAVAL") end
    if EntityCategoryContains(categories.STRUCTURE, unit) then table.insert(tags, "STRUCTURE") end
    if EntityCategoryContains(categories.MASSEXTRACTION, unit) then table.insert(tags, "MASSEXTRACTION") end
    if EntityCategoryContains(categories.ENERGYPRODUCTION, unit) then table.insert(tags, "ENERGYPRODUCTION") end
    if EntityCategoryContains(categories.DIRECTFIRE, unit) then table.insert(tags, "DIRECTFIRE") end
    if EntityCategoryContains(categories.ANTIAIR, unit) then table.insert(tags, "ANTIAIR") end
    if EntityCategoryContains(categories.DEFENSE, unit) then table.insert(tags, "DEFENSE") end
    return tags
end

-- ============================================================
-- Collect State Snapshot
-- ============================================================
local function CollectState(aiBrain)
    local state = {
        step = _G.PyAgent_Bridge.StepId,
        army_index = _G.PyAgent_Bridge.ArmyIndex,
        game_time = GetGameTimeSeconds(),
        game_tick = GetGameTick(),
        is_over = IsGameOver(),
        economy = {
            mass = {
                stored = aiBrain:GetEconomyStored('MASS'),
                income = aiBrain:GetEconomyIncome('MASS'),
                usage = aiBrain:GetEconomyUsage('MASS')
            },
            energy = {
                stored = aiBrain:GetEconomyStored('ENERGY'),
                income = aiBrain:GetEconomyIncome('ENERGY'),
                usage = aiBrain:GetEconomyUsage('ENERGY')
            }
        },
        units = {}
    }

    local myUnits = aiBrain:GetListOfUnits(categories.ALLUNITS, false)
    if myUnits then
        for _, u in ipairs(myUnits) do
            if not u:IsDead() then
                local pos = u:GetPosition()
                local bp = u:GetBlueprint()
                table.insert(state.units, {
                    id = u:GetEntityId(),
                    bp = bp.BlueprintId,
                    pos = { math.floor(pos[1]*10)/10, math.floor(pos[2]*10)/10, math.floor(pos[3]*10)/10 },
                    hp = u:GetHealth(),
                    fraction = u:GetFractionComplete(),
                    tags = GetUnitTags(u)
                })
            end
        end
    end
    return state
end

-- ============================================================
-- Autonomous Scripted Mission Controller
-- Orders:
-- 1. ACU builds T1 Factory
-- 2. ACU builds 2 Mass Extractors
-- 3. ACU builds 4 Power Generators
-- 4. ACU builds 2 Mass Extractors
-- 5. ACU builds 4 Power Generators
-- 6. Factory builds 5 T1 Engineers
-- 7. Eng 1: Builds Anti-Air (AA)
-- 8. Eng 2: Builds Point Defense (PD)
-- 9. Eng 3: Builds Walls around PD
-- 10. Eng 4: Builds Walls around AA
-- 11. Eng 5: Reclaims trees, rocks, wrecks around base
-- ============================================================
local function FindValidBuildPosOffset(aiBrain, blueprintId, nearPos, offsetX, offsetZ)
    local x = math.floor(nearPos[1] + offsetX)
    local z = math.floor(nearPos[3] + offsetZ)
    local y = GetTerrainHeight(x, z)
    local testPos = { x, y, z }
    if aiBrain:CanBuildStructureAt(blueprintId, testPos) then
        return testPos
    end
    for r = 2, 20, 2 do
        for angle = 0, 315, 45 do
            local rad = angle * (math.pi / 180)
            local tx = math.floor(x + math.cos(rad) * r)
            local tz = math.floor(z + math.sin(rad) * r)
            local ty = GetTerrainHeight(tx, tz)
            local tPos = { tx, ty, tz }
            if aiBrain:CanBuildStructureAt(blueprintId, tPos) then
                return tPos
            end
        end
    end
    return testPos
end

local Mission = {
    Initialized = false,
    ACUOrdersIssued = false,
    FactoryQueued = false,
    AssignedEngineers = {},
    ProcessedEngCount = 0,
    PDPos = nil,
    AAPos = nil,
    SortedMassSpots = {}
}

local function RunAutonomousMission(aiBrain, factionIndex)
    local bps = FACTION_BLUEPRINTS[factionIndex] or FACTION_BLUEPRINTS[3]

    local acus = aiBrain:GetListOfUnits(categories.COMMAND, false)
    if not acus or not acus[1] or acus[1]:IsDead() then return end
    local acu = acus[1]
    local acuPos = acu:GetPosition()

    -- 1. Setup Mass Spots
    if not Mission.Initialized then
        Mission.Initialized = true
        Mission.SortedMassSpots = {}

        local markers = ScenarioUtils.GetMarkers()
        if markers then
            for name, marker in pairs(markers) do
                if marker.type == 'Mass' and marker.position then
                    table.insert(Mission.SortedMassSpots, marker.position)
                end
            end
        end

        table.sort(Mission.SortedMassSpots, function(a, b)
            local d1 = (a[1] - acuPos[1])^2 + (a[3] - acuPos[3])^2
            local d2 = (b[1] - acuPos[1])^2 + (b[3] - acuPos[3])^2
            return d1 < d2
        end)

        LOG(string.format("PyAgent Mission: Found %d mass spots. Initializing build queue...", table.getn(Mission.SortedMassSpots)))
    end

    -- 2. Issue ACU Build Order Queue (ONCE)
    if not Mission.ACUOrdersIssued then
        Mission.ACUOrdersIssued = true

        LOG("PyAgent Mission: Issuing ACU build orders...")

        -- Land Factory (find valid build position at offset from ACU)
        local facPos = FindValidBuildPosOffset(aiBrain, bps.factory, acuPos, 12, 12)
        LOG(string.format("PyAgent Mission: Land Factory position validated at (%.1f, %.1f)", facPos[1], facPos[3]))
        IssueBuildMobile({ acu }, facPos, bps.factory, {})

        -- 2 Mass Extractors
        if Mission.SortedMassSpots[1] then
            local s1 = Mission.SortedMassSpots[1]
            local mpos1 = { s1[1], GetTerrainHeight(s1[1], s1[3]), s1[3] }
            IssueBuildMobile({ acu }, mpos1, bps.mex, {})
        end
        if Mission.SortedMassSpots[2] then
            local s2 = Mission.SortedMassSpots[2]
            local mpos2 = { s2[1], GetTerrainHeight(s2[1], s2[3]), s2[3] }
            IssueBuildMobile({ acu }, mpos2, bps.mex, {})
        end

        -- 4 Power Generators (Row 1 near factory)
        local p1 = FindValidBuildPosOffset(aiBrain, bps.pgen, facPos, 6, 0)
        local p2 = FindValidBuildPosOffset(aiBrain, bps.pgen, facPos, 9, 0)
        local p3 = FindValidBuildPosOffset(aiBrain, bps.pgen, facPos, 6, 3)
        local p4 = FindValidBuildPosOffset(aiBrain, bps.pgen, facPos, 9, 3)
        IssueBuildMobile({ acu }, p1, bps.pgen, {})
        IssueBuildMobile({ acu }, p2, bps.pgen, {})
        IssueBuildMobile({ acu }, p3, bps.pgen, {})
        IssueBuildMobile({ acu }, p4, bps.pgen, {})

        -- 2 Mass Extractors
        if Mission.SortedMassSpots[3] then
            local s3 = Mission.SortedMassSpots[3]
            local mpos3 = { s3[1], GetTerrainHeight(s3[1], s3[3]), s3[3] }
            IssueBuildMobile({ acu }, mpos3, bps.mex, {})
        end
        if Mission.SortedMassSpots[4] then
            local s4 = Mission.SortedMassSpots[4]
            local mpos4 = { s4[1], GetTerrainHeight(s4[1], s4[3]), s4[3] }
            IssueBuildMobile({ acu }, mpos4, bps.mex, {})
        end

        -- 4 Power Generators (Row 2 near factory)
        local p5 = FindValidBuildPosOffset(aiBrain, bps.pgen, facPos, -6, 0)
        local p6 = FindValidBuildPosOffset(aiBrain, bps.pgen, facPos, -9, 0)
        local p7 = FindValidBuildPosOffset(aiBrain, bps.pgen, facPos, -6, -3)
        local p8 = FindValidBuildPosOffset(aiBrain, bps.pgen, facPos, -9, -3)
        IssueBuildMobile({ acu }, p5, bps.pgen, {})
        IssueBuildMobile({ acu }, p6, bps.pgen, {})
        IssueBuildMobile({ acu }, p7, bps.pgen, {})
        IssueBuildMobile({ acu }, p8, bps.pgen, {})

        LOG("PyAgent Mission: ACU opening queue completed: Factory -> 2 Mex -> 4 PGen -> 2 Mex -> 4 PGen")
    end

    -- 3. Check Land Factory Completion and Queue 5 Engineers
    local factories = aiBrain:GetListOfUnits(categories.FACTORY * categories.LAND, false)
    if factories and factories[1] and not Mission.FactoryQueued then
        local fac = factories[1]
        if fac:GetFractionComplete() >= 1.0 and not fac:IsDead() then
            LOG("PyAgent Mission: Land Factory is READY! Queueing 5 Engineers...")
            IssueBuildFactory({ fac }, bps.engineer, 5)
            Mission.FactoryQueued = true
        end
    end

    -- 4. Track and Task Each of the 5 Engineers as they are built
    local allEngs = aiBrain:GetListOfUnits(categories.ENGINEER - categories.COMMAND, false)
    if allEngs then
        for _, eng in ipairs(allEngs) do
            local eid = eng:GetEntityId()
            if not eng:IsDead() and eng:GetFractionComplete() >= 1.0 and not Mission.AssignedEngineers[eid] then
                Mission.ProcessedEngCount = Mission.ProcessedEngCount + 1
                local engNum = Mission.ProcessedEngCount
                Mission.AssignedEngineers[eid] = engNum

                LOG(string.format("PyAgent Mission: Engineer #%d (ID %d) ready for assignment!", engNum, eid))

                -- Engineer 1: Builds Anti-Air (AA)
                if engNum == 1 then
                    Mission.AAPos = FindValidBuildPosOffset(aiBrain, bps.aa, acuPos, -10, 14)
                    LOG(string.format("PyAgent Mission: Eng #1 -> Building Anti-Air at (%.1f, %.1f)", Mission.AAPos[1], Mission.AAPos[3]))
                    IssueBuildMobile({ eng }, Mission.AAPos, bps.aa, {})

                -- Engineer 2: Builds Point Defense (PD)
                elseif engNum == 2 then
                    Mission.PDPos = FindValidBuildPosOffset(aiBrain, bps.pd, acuPos, 14, 8)
                    LOG(string.format("PyAgent Mission: Eng #2 -> Building Point Defense at (%.1f, %.1f)", Mission.PDPos[1], Mission.PDPos[3]))
                    IssueBuildMobile({ eng }, Mission.PDPos, bps.pd, {})

                -- Engineer 3: Builds Walls around Point Defense
                elseif engNum == 3 then
                    local center = Mission.PDPos or FindValidBuildPosOffset(aiBrain, bps.pd, acuPos, 14, 8)
                    LOG(string.format("PyAgent Mission: Eng #3 -> Building Walls around PD at (%.1f, %.1f)", center[1], center[3]))
                    local cx, cz = center[1], center[3]
                    local wallOffsets = {
                        { 2.5, 0 }, { -2.5, 0 }, { 0, 2.5 }, { 0, -2.5 },
                        { 2.5, 2.5 }, { -2.5, -2.5 }, { 2.5, -2.5 }, { -2.5, 2.5 }
                    }
                    for _, off in ipairs(wallOffsets) do
                        local wx = cx + off[1]
                        local wz = cz + off[2]
                        local wpos = { wx, GetTerrainHeight(wx, wz), wz }
                        IssueBuildMobile({ eng }, wpos, bps.wall, {})
                    end

                -- Engineer 4: Builds Walls around Anti-Air
                elseif engNum == 4 then
                    local center = Mission.AAPos or FindValidBuildPosOffset(aiBrain, bps.aa, acuPos, -10, 14)
                    LOG(string.format("PyAgent Mission: Eng #4 -> Building Walls around AA at (%.1f, %.1f)", center[1], center[3]))
                    local cx, cz = center[1], center[3]
                    local wallOffsets = {
                        { 2.5, 0 }, { -2.5, 0 }, { 0, 2.5 }, { 0, -2.5 },
                        { 2.5, 2.5 }, { -2.5, -2.5 }, { 2.5, -2.5 }, { -2.5, 2.5 }
                    }
                    for _, off in ipairs(wallOffsets) do
                        local wx = cx + off[1]
                        local wz = cz + off[2]
                        local wpos = { wx, GetTerrainHeight(wx, wz), wz }
                        IssueBuildMobile({ eng }, wpos, bps.wall, {})
                    end

                -- Engineer 5: Reclaims trees, rocks, wrecks around the base
                elseif engNum >= 5 then
                    LOG("PyAgent Mission: Eng #5 -> Starting Reclaim operations around the base...")
                    local rect = Rect(acuPos[1] - 90, acuPos[3] - 90, acuPos[1] + 90, acuPos[3] + 90)
                    local reclaimables = GetReclaimablesInRect(rect)
                    local count = 0
                    if reclaimables then
                        for _, prop in ipairs(reclaimables) do
                            if prop and not IsDestroyed(prop) and ((prop.MaxMassReclaim and prop.MaxMassReclaim > 0) or (prop.MaxEnergyReclaim and prop.MaxEnergyReclaim > 0)) then
                                IssueReclaim({ eng }, prop)
                                count = count + 1
                                if count >= 35 then break end
                            end
                        end
                    end
                    LOG(string.format("PyAgent Mission: Eng #5 queued %d reclaim targets!", count))
                end
            end
        end
    end
end

-- ============================================================
-- Execute External Python Command
-- ============================================================
local function ExecuteCommand(cmd)
    if not cmd or not cmd.type then return end
    local ctype = cmd.type

    if ctype == "move" and cmd.units and cmd.target then
        local units = {}
        for _, id in ipairs(cmd.units) do
            local u = GetUnitById(id)
            if u and not u:IsDead() then table.insert(units, u) end
        end
        if table.getn(units) > 0 then
            IssueMove(units, { cmd.target[1], cmd.target[2] or 0, cmd.target[3] })
        end

    elseif ctype == "build_mobile" and cmd.builder and cmd.blueprint and cmd.target then
        local b = GetUnitById(cmd.builder)
        if b and not b:IsDead() then
            IssueBuildMobile({ b }, { cmd.target[1], cmd.target[2] or 0, cmd.target[3] }, cmd.blueprint, {})
        end

    elseif ctype == "build_factory" and cmd.factory and cmd.blueprint then
        local f = GetUnitById(cmd.factory)
        if f and not f:IsDead() then
            IssueBuildFactory({ f }, cmd.blueprint, cmd.count or 1)
        end

    elseif ctype == "reclaim" and cmd.builder then
        local b = GetUnitById(cmd.builder)
        if b and not b:IsDead() and cmd.target_id then
            local t = GetEntityById(cmd.target_id)
            if t then IssueReclaim({ b }, t) end
        end
    end
end

-- ============================================================
-- Read External Commands via doscript
-- ============================================================
local function ReadAndExecuteCommands()
    local ok = pcall(doscript, _G.PyAgent_Bridge.CMD_PATH)
    if ok and _G.PYAGENT_COMMANDS then
        local data = _G.PYAGENT_COMMANDS
        if data.seq and data.seq > _G.PyAgent_Bridge.LastCmdSeq and data.commands then
            _G.PyAgent_Bridge.LastCmdSeq = data.seq
            for _, cmd in ipairs(data.commands) do
                pcall(ExecuteCommand, cmd)
            end
        end
    end
end

-- ============================================================
-- Main Sim Bridge Thread
-- ============================================================
function _G.PyAgent_Bridge.Start()
    if _G.PyAgent_Bridge.Running then return end
    _G.PyAgent_Bridge.Running = true

    local self = _G.PyAgent_Bridge
    LOG(string.format("PyAgent: Bridge starting on Army %d...", self.ArmyIndex))

    -- Wait 30 ticks for ACU landing animation to finish
    WaitTicks(30)

    local aiBrain = GetArmyBrain(self.ArmyIndex)
    local factionIndex = aiBrain and aiBrain:GetFactionIndex() or 3
    LOG(string.format("PyAgent: Controlled Army=%d, Faction=%d", self.ArmyIndex, factionIndex))

    while not IsGameOver() do
        self.StepId = self.StepId + 1

        local brain = GetArmyBrain(self.ArmyIndex)
        if brain then
            -- 1. Execute autonomous mission steps
            RunAutonomousMission(brain, factionIndex)

            -- 2. Emit state to game.log
            local state = CollectState(brain)
            local stateJson = SerializeJson(state)
            LOG("##PYAGENT_STATE##" .. stateJson)
        end

        -- 3. Execute external commands if any
        ReadAndExecuteCommands()

        -- Advance simulation (10 sim ticks = 1 second at 1.0x speed)
        WaitTicks(self.TickInterval)
    end

    LOG("PyAgent: Bridge session finished.")
    _G.PyAgent_Bridge.Running = false
end
