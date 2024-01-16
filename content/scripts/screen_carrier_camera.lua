g_is_exit = false
g_state_counter = 0
g_vehicle_id = 0

function update(screen_w, screen_h, ticks)

    do_tacview()

    if update_get_is_focus_local() then
        g_state_counter = g_state_counter + 1
    else
        g_state_counter = 0
    end

    if g_state_counter > 1 then
        if g_is_exit then
            if g_vehicle_id ~= 0 then
                g_vehicle_id = 0
                g_state_counter = 0
            else
                g_is_exit = false
                g_state_counter = 0
                update_set_screen_state_exit()
            end
        elseif update_get_is_focus_local() and update_get_screen_state_active() then
            local vehicle = update_get_screen_vehicle()
    
            if vehicle:get() and g_vehicle_id ~= vehicle:get_id() then
                g_state_counter = 0
                g_vehicle_id = vehicle:get_id() 
            end
        end
    end
    
    update_set_screen_vehicle_control_id(g_vehicle_id)
    
    update_ui_rectangle(7, 6, screen_w / 2 - 9, screen_h - 13, color8(64, 128, 255, 255))
    update_ui_rectangle(screen_w / 2 + 2, 6, screen_w / 2 - 9, screen_h - 13, color8(64, 128, 255, 255))
end

function input_event(event, action)
    if action == e_input_action.release then
        if event == e_input.back then
            g_is_exit = true
            g_state_counter = 0
        end
    end
end


g_last_tacview_tick = 0
g_tacview_fps_goal = 3
g_tacview_thread = tostring( {} ):sub(8) -- extracts the "address" part
g_tacview_debug = 1
g_tacview_errors = {}
g_tacview_skip = false
g_tacview_drydock = nil

function tacview_table_contains(tab, needle)
    for _, v in pairs(tab) do
        if v == needle then
            return true
        end
    end
end

function tacview_debug_pcall(callable)
    local success, err = pcall(callable)
    if g_tacview_debug == 1 then
        if not success then
            pcall(function()
                local errmsg = string.format("tacview %s error: %s", g_tacview_thread, err)
                if not tacview_table_contains(g_tacview_errors, errmsg) then
                    print(errmsg)
                end
                g_tacview_errors[#g_tacview_errors+1] = errmsg
            end)
        end
    end
    return success, err
end


function format_time(time)
    local seconds = math.floor(time) % 60
    local minutes = math.floor(time / 60) % 60
    local hours = math.min(math.floor(time / 60 / 60), 99)

    return string.format("%02.f:%02.f:%02.f", hours, minutes, seconds)
end

function tacview_out(msg)
    tacview_debug_pcall(function()
        print(string.format("tac:%s", msg))
    end)
end

function get_drydock()
    -- get any drydock
    local vehicle_count = update_get_map_vehicle_count()
    for i = 0, vehicle_count - 1, 1 do
        local vehicle = update_get_map_vehicle_by_index(i)
        if vehicle:get() then
            local def = vehicle:get_definition_index()
            if def == e_game_object_type.drydock then
                g_tacview_drydock = vehicle:get_id()
                return
            end
        end
    end
end

function get_altitude(vid)
    local vect = update_get_map_vehicle_position_relate_to_parent_vehicle(g_tacview_drydock, vid)
    return vect:y()
end

function do_tacview()
    local st, err = pcall(_do_tacview)
    if not st then
        print(err)
    end
end

function _do_tacview()
    if g_tacview_skip then
        return
    end

    if g_tacview_drydock == nil then
        get_drydock()
    end

    local now = update_get_logic_tick() / 30

    if g_last_tacview_tick == 0 then
        print("start tacview adapter .." .. g_tacview_thread )
    end

    local next_tacview_frame = g_last_tacview_tick + (g_tacview_fps_goal/30)

    if now < next_tacview_frame then
        return
    end
    if g_last_tacview_tick == 0 then
        -- return if we aren't the lifeboat
        local screen_vehicle = update_get_screen_vehicle()
        if screen_vehicle:get() then
            if screen_vehicle:get_definition_index() ~= e_game_object_type.chassis_sea_lifeboat then
                g_tacview_skip = true
                return
            else
                print(string.format("tacview %s adapter on lifeboat screen", g_tacview_thread))
            end
        end
    end

    g_last_tacview_tick = now
    tacview_out(string.format("t=%f", now))

    function try_get_details(v, k, vid)
        local v_def = v:get_definition_index()
        local v_team = v:get_team()
        tacview_out(string.format("%s%s:def=%d,team=%d", k, vid, v_def, v_team))
        local parent = v:get_attached_parent_id()
        local docked = parent > 0
        tacview_out(string.format("%s%s:docked=%s", k, vid, docked))

        local fwd = v:get_direction()
        local bearing = ((90 - math.atan(fwd:y(), fwd:x()) / math.pi * 180) + 360) % 360
        tacview_out(string.format("%s%s:hdg=%f", k, vid, bearing))
    end

    function try_get_position(v, k, vid)
        local v_xz = v:get_position_xz()
        local alt = get_altitude(vid)
        tacview_out(string.format("%s%s:x=%f,y=%f,alt=%f", k, vid, v_xz:x(), v_xz:y(), alt))
    end

    function try_get_visible(v)
        local st, ret = tacview_debug_pcall(function()
            return v:get_is_visible()
        end)
        if st then
            return ret
        end
        return false
    end

    local ret, err = tacview_debug_pcall(function()
        local vehicle_count = update_get_map_vehicle_count()

        for i = 0, vehicle_count - 1, 1 do
            local vehicle = update_get_map_vehicle_by_index(i)
            if vehicle:get() then
                local v_team = vehicle:get_team()
                local visible = update_get_screen_team_id() == v_team

                if not visible then
                    visible = vehicle:get_is_visible()
                end
                if visible then
                    try_get_details(vehicle, "u", vehicle:get_id())
                    try_get_position(vehicle, "u", vehicle:get_id())
                end
            end
        end

        tacview_debug_pcall(function()
            local island_count = update_get_tile_count()

            for i = 0, island_count - 1 do
                local island = update_get_tile_by_index(i)

                if island:get() then
                    local command_center_count = island:get_command_center_count()
                    local island_owner = island:get_team_control()
                    for j = 0, command_center_count - 1 do
                        local command_center_pos_xz = island:get_command_center_position(j)
                        tacview_out(string.format("b%d:x=%f,y=%f,team=%d", i, command_center_pos_xz:x(), command_center_pos_xz:y(), island_owner))
                    end
                end
            end
        end)

        tacview_debug_pcall(function()
            local destroyed_vehicle_count = update_get_map_destroyed_vehicle_count()

            for i = 0, destroyed_vehicle_count - 1, 1 do
                local destroyed_vehicle = update_get_map_destroyed_vehicle(i)

                if destroyed_vehicle:get() then
                    local destroyed_vehicle_position = destroyed_vehicle:get_position_xz(i)
                    local destroyed_vehicle_team_id = destroyed_vehicle:get_team(i)
                    local destroyed_vehicle_factor = destroyed_vehicle:get_factor(i)
                    tacview_out(string.format("x%d:x=%f,y=%f,team=%d,factor=%f", i, destroyed_vehicle_position:x(), destroyed_vehicle_position:y(), destroyed_vehicle_team_id, destroyed_vehicle_factor))
                end
            end
        end)


    end)

    if ret == false then
        print(string.format("err:%s", err))
    end
end
