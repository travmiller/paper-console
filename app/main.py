async def trigger_channel(position: int):
    """
    Executes all modules assigned to a specific channel position.
    """
    # Reset printer buffer at start of print job (for invert mode)
    if hasattr(printer, 'reset_buffer'):
        printer.reset_buffer()
    
    # Get the full ChannelConfig object
    channel = settings.channels.get(position)
    
    if not channel:
        print(f"[SYSTEM] Invalid channel config for position {position}")
        return
    
    # New format: multiple modules
    if channel.modules:
        print(f"[EVENT] Triggered Channel {position} -> {len(channel.modules)} module(s)")
        
        # Sort modules by order
        sorted_modules = sorted(channel.modules, key=lambda m: m.order)
        
        for assignment in sorted_modules:
            module = settings.modules.get(assignment.module_id)
            if module:
                execute_module(module)
                # Add a separator between modules
                if assignment != sorted_modules[-1]:
                    printer.feed(1)
            else:
                print(f"[ERROR] Module {assignment.module_id} not found in module registry")
        
        # Add cutter feed lines at the end of the print job
        feed_lines = getattr(settings, 'cutter_feed_lines', 3)
        
        # If invert is enabled, we must flush the buffer now, regardless of feed lines
        if hasattr(printer, 'invert') and printer.invert and hasattr(printer, 'flush_buffer'):
            printer.flush_buffer()

        # Feed paper directly at the end of print job (bypasses any buffering)
        if feed_lines > 0:
            # Feed paper directly (same for both inverted and normal mode)
            printer.feed_direct(feed_lines)
            print(f"[SYSTEM] Added {feed_lines} feed line(s) to clear cutter")
        return
    
    print(f"[SYSTEM] Channel {position} has no modules assigned")
