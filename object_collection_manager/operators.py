# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2011, Ryan Inch

import bpy

from copy import deepcopy

from bpy.types import (
    Operator,
)

from bpy.props import (
    BoolProperty,
    StringProperty,
    IntProperty
)

from .internals import (
    expanded,
    layer_collections,
    update_property_group,
    send_report,
)

rto_history = {
    "exclude": {},
    "exclude_all": {},
    "select": {},
    "select_all": {},
    "hide": {},
    "hide_all": {},
    "disable": {},
    "disable_all": {},
    "render": {},
    "render_all": {}
}

class ExpandAllOperator(Operator):
    '''Expand/Collapse all collections'''
    bl_label = "Expand All Items"
    bl_idname = "view3d.expand_all_items"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if len(expanded) > 0:
            expanded.clear()
        else:
            for laycol in layer_collections.values():
                if laycol["ptr"].children:
                    expanded.append(laycol["name"])

        # update tree view
        update_property_group(context)

        return {'FINISHED'}


class ExpandSublevelOperator(Operator):
    '''  * Shift-Click to expand/collapse all sublevels'''
    bl_label = "Expand Sublevel Items"
    bl_idname = "view3d.expand_sublevel"
    bl_options = {'REGISTER', 'UNDO'}

    expand: BoolProperty()
    name: StringProperty()
    index: IntProperty()

    def invoke(self, context, event):
        if event.shift:
            # expand/collapse all subcollections
            expand = None

            # check whether to expand or collapse
            if self.name in expanded:
                expanded.remove(self.name)
                expand = False
            else:
                expanded.append(self.name)
                expand = True

            # do expanding/collapsing
            def loop(laycol):
                for item in laycol.children:
                    if expand:
                        if not item.name in expanded:
                            expanded.append(item.name)
                    else:
                        if item.name in expanded:
                            expanded.remove(item.name)

                    if len(item.children) > 0:
                        loop(item)

            loop(layer_collections[self.name]["ptr"])

        else:
            # expand/collapse collection
            if self.expand:
                expanded.append(self.name)
            else:
                expanded.remove(self.name)


        # set selected row to the collection you're expanding/collapsing and update tree view
        context.scene.CMListIndex = self.index
        update_property_group(context)

        return {'FINISHED'}


class CMSetCollectionOperator(Operator):
    '''  * Click to move object to collection.\n  * Shift-Click to add/remove object from collection'''
    bl_label = "Set Object Collection"
    bl_idname = "view3d.set_collection"
    bl_options = {'REGISTER', 'UNDO'}

    collection_index: IntProperty()
    collection_name: StringProperty()

    def invoke(self, context, event):
        collection = layer_collections[self.collection_name]["ptr"].collection

        if event.shift:
            # add object to collection

            # check if in collection
            if context.active_object.name not in collection.objects:
                # add to collection
                bpy.ops.object.link_to_collection(collection_index=self.collection_index)

            else:
                # check and disallow removing from all collections
                for obj in context.selected_objects:
                    if len(obj.users_collection) == 1:
                        send_report("Error removing 1 or more objects from this collection.\nObjects would be left without a collection")

                        return {'FINISHED'}

                # remove from collection
                bpy.ops.collection.objects_remove(collection=collection.name)

        else:
            # move object to collection
            bpy.ops.object.move_to_collection(collection_index=self.collection_index)

        return {'FINISHED'}


class CMExcludeOperator(Operator):
    '''  * Shift-Click to isolate/restore previous state\n  * Ctrl-Click to toggle children'''
    bl_label = "Exclude Collection from View Layer"
    bl_idname = "view3d.exclude_collection"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name
        laycol_ptr = layer_collections[self.name]["ptr"]

        if not view_layer in rto_history["exclude"]:
            rto_history["exclude"][view_layer] = {"target": "", "history": []}

        rto_history["exclude"][view_layer]["target"] = self.name
        exclude_history = rto_history["exclude"][view_layer]["history"]

        if event.shift:
            # isolate/de-isolate exclusion of collections

            # get active layer collections
            active_layer_collections = [x for x in layer_collections.values() \
                                          if x["ptr"].exclude == False]

            # check if collection isolated
            if len(active_layer_collections) == 1 and active_layer_collections[0]["name"] == self.name:
                if len(exclude_history) > 0:
                    # restore previous state
                    for x, item in enumerate(layer_collections.values()):
                        item["ptr"].exclude = exclude_history[x]

                else:
                    # enable all collections
                    for item in layer_collections.values():
                        item["ptr"].exclude = False

                # reset exclude history
                del rto_history["exclude"][view_layer]

            else:
                # isolate collection

                # reset exclude history
                exclude_history.clear()

                # save state
                for item in layer_collections.values():
                    exclude_history.append(item["ptr"].exclude)

                # isolate collection
                for item in layer_collections.values():
                    if item["name"] != laycol_ptr.name:
                        item["ptr"].exclude = True

                laycol_ptr.exclude = False

                # exclude all children
                laycol_iter_list = [laycol_ptr.children]
                while len(laycol_iter_list) > 0:
                    new_laycol_iter_list = []
                    for laycol_iter in laycol_iter_list:
                        for layer_collection in laycol_iter:
                            layer_collection.exclude = True
                            if len(layer_collection.children) > 0:
                                new_laycol_iter_list.append(layer_collection.children)

                    laycol_iter_list = new_laycol_iter_list


        elif event.ctrl:
            # toggle children

            # reset exclude history
            del rto_history["exclude"][view_layer]

            # toggle exclusion of collection (this propagates to children)
            laycol_ptr.exclude = not laycol_ptr.exclude

        else:
            # toggle exclusion

            # reset exclude history
            del rto_history["exclude"][view_layer]


            # get current child exclusion state
            child_exclusion = []

            laycol_iter_list = [laycol_ptr.children]
            while len(laycol_iter_list) > 0:
                new_laycol_iter_list = []
                for laycol_iter in laycol_iter_list:
                    for layer_collection in laycol_iter:
                        child_exclusion.append([layer_collection, layer_collection.exclude])
                        if len(layer_collection.children) > 0:
                            new_laycol_iter_list.append(layer_collection.children)

                laycol_iter_list = new_laycol_iter_list


            # toggle exclusion of collection
            laycol_ptr.exclude = not laycol_ptr.exclude


            # set correct state for all children
            for laycol in child_exclusion:
                laycol[0].exclude = laycol[1]


        # reset exclude all history
        if view_layer in rto_history["exclude_all"]:
            del rto_history["exclude_all"][view_layer]

        return {'FINISHED'}


class CMUnExcludeAllOperator(Operator):
    '''  * Click to toggle between current excluded state and all included.\n  * Shift-Click to invert excluded status of all collections'''
    bl_label = "Toggle Excluded Status Of All Collections"
    bl_idname = "view3d.un_exclude_all_collections"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name

        if not view_layer in rto_history["exclude_all"]:
            rto_history["exclude_all"][view_layer] = []

        exclude_all_history = rto_history["exclude_all"][view_layer]

        if len(exclude_all_history) == 0:
            exclude_all_history.clear()
            keep_history = False

            if event.shift:
                for item in layer_collections.values():
                    keep_history = True
                    exclude_all_history.append(item["ptr"].exclude)

                for x, item in enumerate(layer_collections.values()):
                    item["ptr"].exclude = not exclude_all_history[x]

            else:
                for item in reversed(list(layer_collections.values())):
                    if item["ptr"].exclude:
                        keep_history = True

                    exclude_all_history.append(item["ptr"].exclude)

                    item["ptr"].exclude = False

                exclude_all_history.reverse()

            if not keep_history:
                del rto_history["exclude_all"][view_layer]

        else:
            for x, item in enumerate(layer_collections.values()):
                item["ptr"].exclude = exclude_all_history[x]

            del rto_history["exclude_all"][view_layer]

        return {'FINISHED'}


class CMRestrictSelectOperator(Operator):
    '''  * Shift-Click to isolate/restore previous state\n  * Ctrl-Click to toggle children'''
    bl_label = "Disable Selection of Collection"
    bl_idname = "view3d.restrict_select_collection"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name
        laycol_ptr = layer_collections[self.name]["ptr"]

        if not view_layer in rto_history["select"]:
            rto_history["select"][view_layer] = {"target": "", "history": []}

        rto_history["select"][view_layer]["target"] = self.name
        select_history = rto_history["select"][view_layer]["history"]

        if event.shift:
            # isolate/de-isolate selectability of collections

            # get active collections
            active_layer_collections = [x for x in layer_collections.values() \
                                          if x["ptr"].collection.hide_select == False]

            layerchain = []
            laycol = layer_collections[self.name]

            # get chain of parents up to top level collection
            while laycol["id"] != 0:
                    layerchain.append(laycol)
                    laycol = laycol["parent"]

            # check if reversed layerchain matches active collections
            if layerchain[::-1] == active_layer_collections:
                if len(select_history) > 0:
                    # restore previous state
                    for x, item in enumerate(layer_collections.values()):
                        item["ptr"].collection.hide_select = select_history[x]

                else:
                    # make all collections selectable
                    for item in layer_collections.values():
                        item["ptr"].collection.hide_select = False

                # reset select history
                del rto_history["select"][view_layer]

            else:
                # reset select history
                select_history.clear()

                # save state
                for item in layer_collections.values():
                    select_history.append(item["ptr"].collection.hide_select)

                # make all collections unselectable
                for item in layer_collections.values():
                    item["ptr"].collection.hide_select = True

                # allow selection of active collection plus parents
                laycol_ptr.collection.hide_select = False

                laycol = layer_collections[self.name]
                while laycol["id"] != 0:
                    laycol["ptr"].collection.hide_select = False
                    laycol = laycol["parent"]


        elif event.ctrl:
            # toggle children

            # reset select history
            del rto_history["select"][view_layer]

            # toggle selectability of collection
            state = not laycol_ptr.collection.hide_select
            laycol_ptr.collection.hide_select = state

            # pass state to children
            laycol_iter_list = [laycol_ptr.children]
            while len(laycol_iter_list) > 0:
                new_laycol_iter_list = []
                for laycol_iter in laycol_iter_list:
                    for layer_collection in laycol_iter:
                        layer_collection.collection.hide_select = state
                        if len(layer_collection.children) > 0:
                            new_laycol_iter_list.append(layer_collection.children)

                laycol_iter_list = new_laycol_iter_list

        else:
            # reset select history
            del rto_history["select"][view_layer]

            # toggle selectability of collection
            laycol_ptr.collection.hide_select = not laycol_ptr.collection.hide_select


        # reset select all history
        if view_layer in rto_history["select_all"]:
            del rto_history["select_all"][view_layer]

        return {'FINISHED'}


class CMUnRestrictSelectAllOperator(Operator):
    '''  * Click to toggle between current selectable state and all selectable.\n  * Shift-Click to invert selectable status of all collections'''
    bl_label = "Toggle Selectable Status Of All Collections"
    bl_idname = "view3d.un_restrict_select_all_collections"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name

        if not view_layer in rto_history["select_all"]:
            rto_history["select_all"][view_layer] = []

        select_all_history = rto_history["select_all"][view_layer]

        if len(select_all_history) == 0:
            select_all_history.clear()
            keep_history = False

            for item in layer_collections.values():
                if event.shift:
                    keep_history = True
                    select_all_history.append(item["ptr"].collection.hide_select)
                    item["ptr"].collection.hide_select = not item["ptr"].collection.hide_select

                else:
                    if item["ptr"].collection.hide_select:
                        keep_history = True

                    select_all_history.append(item["ptr"].collection.hide_select)
                    item["ptr"].collection.hide_select = False

            if not keep_history:
                del rto_history["select_all"][view_layer]

        else:
            for x, item in enumerate(layer_collections.values()):
                item["ptr"].collection.hide_select = select_all_history[x]

            del rto_history["select_all"][view_layer]

        return {'FINISHED'}


class CMHideOperator(Operator):
    '''  * Shift-Click to isolate/restore previous state\n  * Ctrl-Click to toggle children'''
    bl_label = "Hide Collection"
    bl_idname = "view3d.hide_collection"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name
        laycol_ptr = layer_collections[self.name]["ptr"]

        if not view_layer in rto_history["hide"]:
            rto_history["hide"][view_layer] = {"target": "", "history": []}

        rto_history["hide"][view_layer]["target"] = self.name
        hide_history = rto_history["hide"][view_layer]["history"]

        if event.shift:
            # isolate/de-isolate view of collections

            # get active collections
            active_layer_collections = [x for x in layer_collections.values() \
                                          if x["ptr"].hide_viewport == False]

            layerchain = []
            laycol = layer_collections[self.name]

            # get chain of parents up to top level collection
            while laycol["id"] != 0:
                    layerchain.append(laycol)
                    laycol = laycol["parent"]

            # check if reversed layerchain matches active collections
            if layerchain[::-1] == active_layer_collections:
                if len(hide_history) > 0:
                    # restore previous state
                    for x, item in enumerate(layer_collections.values()):
                        item["ptr"].hide_viewport = hide_history[x]

                else:
                    # show all collections
                    for laycol in layer_collections.values():
                        laycol["ptr"].hide_viewport = False

                # reset hide history
                del rto_history["hide"][view_layer]

            else:
                # reset hide history
                hide_history.clear()

                # save state
                for item in layer_collections.values():
                    hide_history.append(item["ptr"].hide_viewport)

                # hide all collections
                for laycol in layer_collections.values():
                    laycol["ptr"].hide_viewport = True

                # show active collection plus parents
                laycol_ptr.hide_viewport = False

                laycol = layer_collections[self.name]
                while laycol["id"] != 0:
                    laycol["ptr"].hide_viewport = False
                    laycol = laycol["parent"]

        elif event.ctrl:
            # toggle children

            # reset hide history
            del rto_history["hide"][view_layer]

            # toggle view of collection
            state = not laycol_ptr.hide_viewport
            laycol_ptr.hide_viewport = state

            # pass state to children
            laycol_iter_list = [laycol_ptr.children]
            while len(laycol_iter_list) > 0:
                new_laycol_iter_list = []
                for laycol_iter in laycol_iter_list:
                    for layer_collection in laycol_iter:
                        layer_collection.hide_viewport = state
                        if len(layer_collection.children) > 0:
                            new_laycol_iter_list.append(layer_collection.children)

                laycol_iter_list = new_laycol_iter_list

        else:
            # reset hide history
            del rto_history["hide"][view_layer]

            # toggle view of collection
            laycol_ptr.hide_viewport = not laycol_ptr.hide_viewport


        # reset hide all history
        if view_layer in rto_history["hide_all"]:
            del rto_history["hide_all"][view_layer]

        return {'FINISHED'}


class CMUnHideAllOperator(Operator):
    '''  * Click to toggle between current visibility state and all visible.\n  * Shift-Click to invert visibility status of all collections'''
    bl_label = "Toggle Hidden Status Of All Collections"
    bl_idname = "view3d.un_hide_all_collections"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name

        if not view_layer in rto_history["hide_all"]:
            rto_history["hide_all"][view_layer] = []

        hide_all_history = rto_history["hide_all"][view_layer]

        if len(hide_all_history) == 0:
            hide_all_history.clear()
            keep_history = False

            for item in layer_collections.values():
                if event.shift:
                    keep_history = True
                    hide_all_history.append(item["ptr"].hide_viewport)
                    item["ptr"].hide_viewport = not item["ptr"].hide_viewport

                else:
                    if item["ptr"].hide_viewport:
                        keep_history = True

                    hide_all_history.append(item["ptr"].hide_viewport)
                    item["ptr"].hide_viewport = False

            if not keep_history:
                del rto_history["hide_all"][view_layer]

        else:
            for x, item in enumerate(layer_collections.values()):
                item["ptr"].hide_viewport = hide_all_history[x]

            del rto_history["hide_all"][view_layer]

        return {'FINISHED'}


class CMDisableViewportOperator(Operator):
    '''  * Shift-Click to isolate/restore previous state\n  * Ctrl-Click to toggle children'''
    bl_label = "Disable Collection in Viewport"
    bl_idname = "view3d.disable_viewport_collection"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name
        laycol_ptr = layer_collections[self.name]["ptr"]

        if not view_layer in rto_history["disable"]:
            rto_history["disable"][view_layer] = {"target": "", "history": []}

        rto_history["disable"][view_layer]["target"] = self.name
        disable_history = rto_history["disable"][view_layer]["history"]

        if event.shift:
            # isolate/de-isolate disablement of collections in viewport

            # get active collections
            active_layer_collections = [x for x in layer_collections.values() \
                                          if x["ptr"].collection.hide_viewport == False]

            layerchain = []
            laycol = layer_collections[self.name]

            # get chain of parents up to top level collection
            while laycol["id"] != 0:
                    layerchain.append(laycol)
                    laycol = laycol["parent"]

            # check if reversed layerchain matches active collections
            if layerchain[::-1] == active_layer_collections:
                if len(disable_history) > 0:
                    # restore previous state
                    for x, item in enumerate(layer_collections.values()):
                        item["ptr"].collection.hide_viewport = disable_history[x]

                else:
                    # enable all collections in viewport
                    for laycol in layer_collections.values():
                        laycol["ptr"].collection.hide_viewport = False

                # reset disable history
                del rto_history["disable"][view_layer]

            else:
                # reset disable history
                disable_history.clear()

                # save state
                for item in layer_collections.values():
                    disable_history.append(item["ptr"].collection.hide_viewport)

                # disable all collections in viewport
                for laycol in layer_collections.values():
                    laycol["ptr"].collection.hide_viewport = True

                # enable active collection plus parents in viewport
                laycol_ptr.collection.hide_viewport = False

                laycol = layer_collections[self.name]
                while laycol["id"] != 0:
                    laycol["ptr"].collection.hide_viewport = False
                    laycol = laycol["parent"]

        elif event.ctrl:
            # toggle children

            # reset disable history
            del rto_history["disable"][view_layer]

            # toggle view of collection
            state = not laycol_ptr.collection.hide_viewport
            laycol_ptr.collection.hide_viewport = state

            # pass state to children
            laycol_iter_list = [laycol_ptr.children]
            while len(laycol_iter_list) > 0:
                new_laycol_iter_list = []
                for laycol_iter in laycol_iter_list:
                    for layer_collection in laycol_iter:
                        layer_collection.collection.hide_viewport = state
                        if len(layer_collection.children) > 0:
                            new_laycol_iter_list.append(layer_collection.children)

                laycol_iter_list = new_laycol_iter_list

        else:
            # reset disable history
            del rto_history["disable"][view_layer]

            # toggle disable of collection in viewport
            laycol_ptr.collection.hide_viewport = not laycol_ptr.collection.hide_viewport


        # reset disable all history
        if view_layer in rto_history["disable_all"]:
            del rto_history["disable_all"][view_layer]

        return {'FINISHED'}


class CMUnDisableViewportAllOperator(Operator):
    '''  * Click to toggle between current viewport display and all enabled.\n  * Shift-Click to invert viewport display of all collections'''
    bl_label = "Toggle Viewport Display of All Collections"
    bl_idname = "view3d.un_disable_viewport_all_collections"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name

        if not view_layer in rto_history["disable_all"]:
            rto_history["disable_all"][view_layer] = []

        disable_all_history = rto_history["disable_all"][view_layer]

        if len(disable_all_history) == 0:
            disable_all_history.clear()
            keep_history = False

            for item in layer_collections.values():
                if event.shift:
                    keep_history = True
                    disable_all_history.append(item["ptr"].collection.hide_viewport)
                    item["ptr"].collection.hide_viewport = not \
                        item["ptr"].collection.hide_viewport

                else:
                    if item["ptr"].collection.hide_viewport:
                        keep_history = True

                    disable_all_history.append(item["ptr"].collection.hide_viewport)
                    item["ptr"].collection.hide_viewport = False

            if not keep_history:
                del rto_history["disable_all"][view_layer]

        else:
            for x, item in enumerate(layer_collections.values()):
                item["ptr"].collection.hide_viewport = disable_all_history[x]

            del rto_history["disable_all"][view_layer]

        return {'FINISHED'}


class CMDisableRenderOperator(Operator):
    '''  * Shift-Click to isolate/restore previous state\n  * Ctrl-Click to toggle children'''
    bl_label = "Disable Collection in Render"
    bl_idname = "view3d.disable_render_collection"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name
        laycol_ptr = layer_collections[self.name]["ptr"]

        if not view_layer in rto_history["render"]:
            rto_history["render"][view_layer] = {"target": "", "history": []}

        rto_history["render"][view_layer]["target"] = self.name
        render_history = rto_history["render"][view_layer]["history"]

        if event.shift:
            # isolate/de-isolate render of collections

            # get active collections
            active_layer_collections = [x for x in layer_collections.values() \
                                          if x["ptr"].collection.hide_render == False]

            layerchain = []
            laycol = layer_collections[self.name]

            # get chain of parents up to top level collection
            while laycol["id"] != 0:
                    layerchain.append(laycol)
                    laycol = laycol["parent"]

            # check if reversed layerchain matches active collections
            if layerchain[::-1] == active_layer_collections:
                if len(render_history) > 0:
                    # restore previous state
                    for x, item in enumerate(layer_collections.values()):
                        item["ptr"].collection.hide_render = render_history[x]

                else:
                    # allow render of all collections
                    for laycol in layer_collections.values():
                        laycol["ptr"].collection.hide_render = False

                # reset render history
                del rto_history["render"][view_layer]

            else:
                # reset render history
                render_history.clear()

                # save state
                for item in layer_collections.values():
                    render_history.append(item["ptr"].collection.hide_render)

                # disallow render of all collections
                for laycol in layer_collections.values():
                    laycol["ptr"].collection.hide_render = True

                # allow render of active collection plus parents
                laycol_ptr.collection.hide_render = False

                laycol = layer_collections[self.name]
                while laycol["id"] != 0:
                    laycol["ptr"].collection.hide_render = False
                    laycol = laycol["parent"]

        elif event.ctrl:
            # toggle children

            # reset render history
            del rto_history["render"][view_layer]

            # toggle view of collection
            state = not laycol_ptr.collection.hide_render
            laycol_ptr.collection.hide_render = state

            # pass state to children
            laycol_iter_list = [laycol_ptr.children]
            while len(laycol_iter_list) > 0:
                new_laycol_iter_list = []
                for laycol_iter in laycol_iter_list:
                    for layer_collection in laycol_iter:
                        layer_collection.collection.hide_render = state
                        if len(layer_collection.children) > 0:
                            new_laycol_iter_list.append(layer_collection.children)

                laycol_iter_list = new_laycol_iter_list

        else:
            # reset render history
            del rto_history["render"][view_layer]

            # toggle renderability of collection
            laycol_ptr.collection.hide_render = not laycol_ptr.collection.hide_render


        # reset render all history
        if view_layer in rto_history["render_all"]:
            del rto_history["render_all"][view_layer]

        return {'FINISHED'}


class CMUnDisableRenderAllOperator(Operator):
    '''  * Click to toggle between current render status and all rendered.\n  * Shift-Click to invert render status of all collections'''
    bl_label = "Toggle Render Status of All Collections"
    bl_idname = "view3d.un_disable_render_all_collections"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        global rto_history

        view_layer = context.view_layer.name

        if not view_layer in rto_history["render_all"]:
            rto_history["render_all"][view_layer] = []

        render_all_history = rto_history["render_all"][view_layer]

        if len(render_all_history) == 0:
            render_all_history.clear()
            keep_history = False

            for item in layer_collections.values():
                if event.shift:
                    keep_history = True
                    render_all_history.append(item["ptr"].collection.hide_render)
                    item["ptr"].collection.hide_render = not \
                        item["ptr"].collection.hide_render

                else:
                    if item["ptr"].collection.hide_render:
                        keep_history = True

                    render_all_history.append(item["ptr"].collection.hide_render)
                    item["ptr"].collection.hide_render = False

            if not keep_history:
                del rto_history["render_all"][view_layer]

        else:
            for x, item in enumerate(layer_collections.values()):
                item["ptr"].collection.hide_render = render_all_history[x]

            del rto_history["render_all"][view_layer]

        return {'FINISHED'}


class CMRemoveCollectionOperator(Operator):
    '''Remove Collection'''
    bl_label = "Remove Collection"
    bl_idname = "view3d.remove_collection"
    bl_options = {'UNDO'}

    collection_name: StringProperty()

    def execute(self, context):
        global rto_history

        laycol = layer_collections[self.collection_name]
        collection = laycol["ptr"].collection
        parent_collection = laycol["parent"]["ptr"].collection


        # shift all objects in this collection to the parent collection
        for obj in collection.objects:
            if obj.name not in parent_collection.objects:
                parent_collection.objects.link(obj)


        # shift all child collections to the parent collection
        if collection.children:
            for subcollection in collection.children:
                parent_collection.children.link(subcollection)


        # remove collection and update tree view
        bpy.data.collections.remove(collection)
        update_property_group(context)


        if len(context.scene.CMListCollection) == context.scene.CMListIndex:
            context.scene.CMListIndex = len(context.scene.CMListCollection) - 1
            update_property_group(context)


        # reset history
        for rto in rto_history.values():
            rto.clear()

        return {'FINISHED'}

rename = [False]
class CMNewCollectionOperator(Operator):
    '''Add New Collection'''
    bl_label = "Add New Collection"
    bl_idname = "view3d.add_collection"
    bl_options = {'UNDO'}

    child: BoolProperty()

    def execute(self, context):
        global rto_history

        new_collection = bpy.data.collections.new('Collection')
        scn = context.scene

        # if there are collections
        if len(scn.CMListCollection) > 0:
            # get selected collection
            laycol = layer_collections[scn.CMListCollection[scn.CMListIndex].name]

            # add new collection
            if self.child:
                laycol["ptr"].collection.children.link(new_collection)
                expanded.append(laycol["name"])

                # update tree view property
                update_property_group(context)

                scn.CMListIndex = layer_collections[new_collection.name]["row_index"]

            else:
                laycol["parent"]["ptr"].collection.children.link(new_collection)

                # update tree view property
                update_property_group(context)

                scn.CMListIndex = layer_collections[new_collection.name]["row_index"]

        # if no collections add top level collection and select it
        else:
            scn.collection.children.link(new_collection)

            # update tree view property
            update_property_group(context)

            scn.CMListIndex = 0

        global rename
        rename[0] = True

        # reset history
        for rto in rto_history.values():
            rto.clear()

        return {'FINISHED'}


phantom_history = {"view_layer": "",
                   "initial_state": {},

                   "exclude_history": {},
                   "select_history": {},
                   "hide_history": {},
                   "disable_history": {},
                   "render_history": {},

                   "exclude_all_history": [],
                   "select_all_history": [],
                   "hide_all_history": [],
                   "disable_all_history": [],
                   "render_all_history": []
                   }

class CMPhantomModeOperator(Operator):
    '''Toggle Phantom Mode'''
    bl_label = "Toggle Phantom Mode"
    bl_idname = "view3d.toggle_phantom_mode"

    def execute(self, context):
        global phantom_history
        global rto_history

        scn = context.scene
        view_layer = context.view_layer.name

        # enter Phantom Mode
        if not scn.CM_Phantom_Mode:

            scn.CM_Phantom_Mode = True

            # save current visibility state
            phantom_history["view_layer"] = view_layer

            laycol_iter_list = [context.view_layer.layer_collection.children]
            while len(laycol_iter_list) > 0:
                new_laycol_iter_list = []
                for laycol_iter in laycol_iter_list:
                    for layer_collection in laycol_iter:
                        phantom_history["initial_state"][layer_collection.name] = {
                            "exclude": layer_collection.exclude,
                            "select": layer_collection.collection.hide_select,
                            "hide": layer_collection.hide_viewport,
                            "disable": layer_collection.collection.hide_viewport,
                            "render": layer_collection.collection.hide_render,
                                }

                        if len(layer_collection.children) > 0:
                            new_laycol_iter_list.append(layer_collection.children)

                laycol_iter_list = new_laycol_iter_list


            # save current rto history
            for rto, history, in rto_history.items():
                if history.get(view_layer, None):
                    phantom_history[rto+"_history"] = deepcopy(history[view_layer])


        # return to normal mode
        else:
            laycol_iter_list = [context.view_layer.layer_collection.children]
            while len(laycol_iter_list) > 0:
                new_laycol_iter_list = []
                for laycol_iter in laycol_iter_list:
                    for layer_collection in laycol_iter:
                        phantom_laycol = phantom_history["initial_state"][layer_collection.name]

                        layer_collection.exclude = \
                            phantom_laycol["exclude"]

                        layer_collection.collection.hide_select = \
                            phantom_laycol["select"]

                        layer_collection.hide_viewport = \
                            phantom_laycol["hide"]

                        layer_collection.collection.hide_viewport = \
                            phantom_laycol["disable"]

                        layer_collection.collection.hide_render = \
                            phantom_laycol["render"]


                        if len(layer_collection.children) > 0:
                            new_laycol_iter_list.append(layer_collection.children)

                laycol_iter_list = new_laycol_iter_list


            # restore previous rto history
            for rto, history, in rto_history.items():
                if view_layer in history:
                    del history[view_layer]

                if phantom_history[rto+"_history"]:
                    history[view_layer] = deepcopy(phantom_history[rto+"_history"])

                phantom_history[rto+"_history"].clear()

            scn.CM_Phantom_Mode = False


        return {'FINISHED'}
