package com.aicraft.craftcommand;

import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.crafting.CraftingInput;
import net.minecraft.world.item.crafting.CraftingRecipe;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.item.crafting.PlacementInfo;
import net.minecraft.world.item.crafting.RecipeHolder;
import net.minecraft.world.item.crafting.RecipeManager;
import net.minecraft.world.item.crafting.ShapedRecipe;

import java.util.ArrayList;
import java.util.List;

public final class CraftingService {
    private CraftingService() {
    }

    public static boolean craft(ServerPlayer player, Item item) {
        ServerLevel level = (ServerLevel) player.level();
        RecipeManager recipeManager = level.recipeAccess();
        Inventory inventory = player.getInventory();

        for (RecipeHolder<?> holder : recipeManager.getRecipes()) {
            if (!(holder.value() instanceof CraftingRecipe recipe)) {
                continue;
            }

            PlacementInfo placement = recipe.placementInfo();
            List<Ingredient> ingredients = placement.ingredients();
            List<ItemStack> selected = new ArrayList<>(ingredients.size());
            boolean hasIngredients = true;

            for (Ingredient ingredient : ingredients) {
                ItemStack matchingStack = findMatchingStack(inventory, ingredient, selected);
                if (matchingStack.isEmpty()) {
                    hasIngredients = false;
                    break;
                }
                selected.add(matchingStack.copyWithCount(1));
            }

            if (!hasIngredients) {
                continue;
            }

            int width = recipe instanceof ShapedRecipe shaped ? shaped.getWidth() : 3;
            int height = recipe instanceof ShapedRecipe shaped ? shaped.getHeight() : 3;
            int slotCount = width * height;
            List<ItemStack> grid = new ArrayList<>(slotCount);
            for (int slot = 0; slot < slotCount; slot++) {
                int ingredientIndex = slot < placement.slotsToIngredientIndex().size()
                        ? placement.slotsToIngredientIndex().getInt(slot)
                        : PlacementInfo.EMPTY_SLOT;
                grid.add(ingredientIndex == PlacementInfo.EMPTY_SLOT
                        ? ItemStack.EMPTY
                        : selected.get(ingredientIndex));
            }

            CraftingInput input = CraftingInput.of(width, height, grid);
            if (!recipe.matches(input, level)) {
                continue;
            }

            ItemStack result = recipe.assemble(input);
            if (result.isEmpty() || result.getItem() != item) {
                continue;
            }

            for (ItemStack ingredientStack : selected) {
                removeOne(inventory, ingredientStack);
            }
            inventory.placeItemBackInInventory(result.copy());
            player.sendSystemMessage(Component.literal("Crafted " + result.getHoverName().getString() + "."));
            return true;
        }

        player.sendSystemMessage(Component.literal("You do not have the ingredients for a recipe that makes that item."));
        return false;
    }

    private static ItemStack findMatchingStack(Inventory inventory, Ingredient ingredient, List<ItemStack> reserved) {
        for (int slot = 0; slot < inventory.getContainerSize(); slot++) {
            ItemStack stack = inventory.getItem(slot);
            int reservedCount = reserved.stream()
                    .filter(item -> item.getItem() == stack.getItem())
                    .mapToInt(ItemStack::getCount)
                    .sum();
            if (stack.isEmpty() || !ingredient.test(stack) || stack.getCount() <= reservedCount) {
                continue;
            }
            return stack;
        }
        return ItemStack.EMPTY;
    }

    private static void removeOne(Inventory inventory, ItemStack target) {
        for (int slot = 0; slot < inventory.getContainerSize(); slot++) {
            ItemStack stack = inventory.getItem(slot);
            if (stack.getItem() == target.getItem() && !stack.isEmpty()) {
                inventory.removeItem(slot, 1);
                return;
            }
        }
    }
}
