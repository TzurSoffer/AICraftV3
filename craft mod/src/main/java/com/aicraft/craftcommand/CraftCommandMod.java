package com.aicraft.craftcommand;

import com.mojang.brigadier.CommandDispatcher;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.item.ItemArgument;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.Item;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import static net.minecraft.commands.Commands.argument;
import static net.minecraft.commands.Commands.literal;

public final class CraftCommandMod implements ModInitializer {
    private static final Logger LOGGER = LoggerFactory.getLogger("craftcommand");

    @Override
    public void onInitialize() {
        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) -> register(dispatcher, registryAccess));
        LOGGER.info("Craft Command loaded");
    }

    private static void register(CommandDispatcher<CommandSourceStack> dispatcher, net.minecraft.commands.CommandBuildContext registryAccess) {
        dispatcher.register(literal("craft")
                .then(argument("itemName", ItemArgument.item(registryAccess))
                .executes(context -> craft(context.getSource(), ItemArgument.getItem(context, "itemName").item().value()))));
    }

    private static int craft(CommandSourceStack source, Item item) {
        ServerPlayer player = source.getPlayer();
        if (player == null) {
            source.sendFailure(net.minecraft.network.chat.Component.literal("This command can only be used by a player."));
            return 0;
        }
        return CraftingService.craft(player, item) ? 1 : 0;
    }
}
