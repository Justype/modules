-- Lmod modulefile.lua
-- Author: Ziyue Cheng
-- Almost all of them are automated, you can modify whatis, ModulesHelp, and APP_HOME as needed.
-- Search TOCHANGE to find the targets.
-- You can also load other modules in this Lmod script.
--     load("java/17.0.12")

local abs_path = myFileName()                   -- absolute path of module, /somewhere/modules/modulefiles/app/x.y.z
local app_full_name = myModuleFullName()        -- full name of module, app/x.y.z
local app_name = app_full_name:match("^(.+)/")  -- app name, app
local app_version = myModuleVersion()           -- app version, x.y.z
local module_root = abs_path:match("^(.+)/.+/.+/")    -- abs path of modules, /somewhere/modules
local app_root = pathJoin(module_root, app_full_name) -- abs path of target app, /somewhere/modules/app/x.y.z
local current_datetime = os.date("%Y-%m-%d %H:%M:%S") -- Record current datetime

-- TOCHANGE: A brief description using whatis
whatis("Loads " .. app_name .. " version " .. app_version)

-- TOCHANGE: Detailed help section
help([[Placeholder for the usage of this module.]])

-- Display a message when loading the module
if (mode() == "load") then
    io.stderr:write("[" .. current_datetime .. "] Loading module " .. app_full_name .. "\n")
end

-- Display a message when unloading the module
if (mode() == "unload") then
    io.stderr:write("[" .. current_datetime .. "] Unloading module " .. app_full_name .. "\n")
end

-- Modify environment variables if the directories exist
if (isDir(pathJoin(app_root, "bin"))) then
    prepend_path("PATH", pathJoin(app_root, "bin"))
else
    io.stderr:write("WARNING: No bin directory found in " .. app_root .. "\n")
end
if (isDir(pathJoin(app_root, "lib"))) then
    prepend_path("LD_LIBRARY_PATH", pathJoin(app_root, "lib"))
end
if (isDir(pathJoin(app_root, "share/man"))) then
    prepend_path("MANPATH", pathJoin(app_root, "share/man"))
end

-- TOCHANGE: Set custom environment variables
-- setenv("APP_HOME", app_root)

-- Handle conflicts with other versions
conflict(app_name)
