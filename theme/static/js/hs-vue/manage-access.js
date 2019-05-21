/**
 * Created by Mauriel on 5/19/2019.
 */

let manageAccessCmp = new Vue({
    el: '#manage-access',
    delimiters: ['${', '}'],
    data: {
        users: USERS_JSON.map(function(user) {
            user.loading = false;
            return user;
        }),
        currentUser: CURRENT_USER_PK,
        selfAccessLevel: SELF_ACCESS_LEVEL,
        quotaHolder: USERS_JSON.find(function(user) {
            return user.id === QUOTA_HOLDER_PK;
        }),
        resType: RES_TYPE,
        resShortId: SHORT_ID,
        canChangeResourceFlags: CAN_CHANGE_RESOURCE_FLAGS,
        groupImageDefaultUrl: GROUP_IMAGE_DEFAULT_URL,
        resourceMode: RESOURCE_MODE,
        resAccess: RESOURCE_ACCESS,
        canBePublicDiscoverable: CAN_BE_PUBLIC_OR_DISCOVERABLE,
        isInviteUsers: true,
        selectedAccess: 'view',
        accessStr: {
            view: 'Can view',
            edit: 'Can edit',
            owner: 'Is owner'
        },
        error: "",
        quotaError: "",
        sharingError: "",
        isProcessing: false,
        isProcessingAccess: false,
        isProcessingShareable: false,
    },
    watch: {
        resAccess: function (newAccess, oldAccess) {
            // TODO: move to Highlight's component once it's ready
            $("#publish").toggleClass("disabled", !newAccess.isPublic);
            $("#publish > span").attr("data-original-title", !newAccess.isPublic ?
                "Publish this resource<small class='space-top'>You must make your resource public in the Manage Access Panel before it can be published." : "Publish this resource");
            $("#publish").attr("data-toggle", !newAccess.isPublic ? "" : "modal");   // Disable the agreement modal

            let accessStr = "Private";
            if (newAccess.isPublic && newAccess.isDiscoverable) {
                accessStr = "Public"
            }
            else if (!newAccess.isPublic && newAccess.isDiscoverable) {
                accessStr = "Discoverable"
            }
            $("#hl-sharing-status").text(accessStr);    // Update highlight sharing status
        }
    },
    computed: {
        hasOnlyOneOwner: function() {
            return this.users.filter(function(user) {
                return user.access === "owner";
            }).length === 1;
        },
    },
    methods: {
        changeAccess: function (user, index, accessToGrant) {
            let vue = this;

            this.error = "";    // Clear errors
            user.loading = true;
            this.isProcessing = true;
            this.users.splice(index, 1, user);

            $.post('/hsapi/_internal/' + this.resShortId + '/share-resource-with-' + user.user_type + '/'
                + accessToGrant + '/' + user.id + '/', function (result) {
                let resp;
                try {
                    resp = JSON.parse(result)
                }
                catch (error) {
                    console.log(error);
                    vue.isProcessing = false;
                    return;
                }

                if (resp.status == "success") {
                    // Access changes to self can't be undone
                    user.can_undo = !(vue.currentUser === user.id);

                    user.access = resp.privilege_granted;
                    vue.users.splice(index, 1, user);
                    if (vue.currentUser === user.id) {
                        vue.selfAccessLevel = user.access;
                    }
                }
                else {
                    console.log(resp);
                    vue.error = resp.error_msg;
                }

                user.loading = false;
                vue.users.splice(index, 1, user);
                vue.isProcessing = false;
            });
        },
        showPermissionDialog: function (user, index, accessToGrant){
            // close the manage access panel (modal)
            $("#manage-access").modal('hide');

            let vue = this;
            // display change share permission confirmation dialog
            $("#dialog-confirm-change-share-permission").dialog({
                resizable: false,
                draggable: false,
                height: "auto",
                width: 500,
                modal: true,
                dialogClass: 'noclose',
                buttons: {
                    Cancel: function () {
                        $(this).dialog("close");
                        // show manage access control panel again
                        $("#manage-access").modal('show');
                    },
                    "Confirm": function () {
                        $(this).dialog("close");
                        $("#manage-access").modal('show');
                        vue.changeAccess(user, index, accessToGrant);
                    }
                },
                open: function () {
                    $(this).closest(".ui-dialog")
                        .find(".ui-dialog-buttonset button:first") // the first button
                        .addClass("btn btn-default");

                    $(this).closest(".ui-dialog")
                        .find(".ui-dialog-buttonset button:nth-child(2)") // the first button
                        .addClass("btn btn-danger");
                }
            });
        },
        showDeleteSelfDialog: function (user, index) {
            // close the manage access panel (modal)
            $("#manage-access ").modal("hide");
            let vue = this;

            // display remove access confirmation dialog
            $("#dialog-confirm-delete-self-access").dialog({
                resizable: false,
                draggable: false,
                height: "auto",
                width: 500,
                modal: true,
                dialogClass: 'noclose',
                buttons: {
                    Cancel: function () {
                        $(this).dialog("close");
                        // show manage access control panel again
                        $("#manage-access").modal('show');
                    },
                    "Remove": function () {
                        $(this).dialog("close");
                        vue.removeAccess(user, index);
                    }
                },
                open: function () {
                    $(this).closest(".ui-dialog")
                        .find(".ui-dialog-buttonset button:first") // the first button
                        .addClass("btn btn-default");

                    $(this).closest(".ui-dialog")
                        .find(".ui-dialog-buttonset button:nth-child(2)") // the second button
                        .addClass("btn btn-danger");
                }
            });
        },
        undoAccess: function (user, index) {
            let vue = this;
            vue.error = "";
            user.loading = true;
            this.users.splice(index, 1, user);

            $.post('/hsapi/_internal/' + this.resShortId + '/undo-share-resource-with-'
                + user.user_type + '/' + user.id + '/', function (resp) {
                if (resp.status === "success") {
                    user.access = resp['undo_' + user.user_type + '_privilege'];
                    user.can_undo = false;
                    if (user.access === "none") {
                        vue.users.splice(index, 1); // The entry was removed
                        return;
                    }
                    else {
                        vue.users.splice(index, 1, user);
                    }
                }
                else {
                    vue.error = resp.error_msg;
                    console.log(resp);
                }

                user.loading = false;
                vue.users.splice(index, 1, user);
                vue.isProcessing = false;
            });
        },
        grantAccess: function () {
            let targetUserId;

            if (this.isInviteUsers) {
                if ($("#user-deck > .hilight").length > 0) {
                    targetUserId = parseInt($("#user-deck > .hilight")[0].getAttribute("data-value"));
                }
                else {
                    return false;   // No user selected
                }
            }
            else {
                if ($("#id_group-deck > .hilight").length > 0) {
                    targetUserId = parseInt($("#id_group-deck > .hilight")[0].getAttribute("data-value"));
                }
                else {
                    return false;   // No group selected
                }
            }

            $(".hilight > span").click(); // Clear the autocomplete
            this.error = "";
            let vue = this;

            let index = -1;
            let user = this.users.filter(function (u, i) {
                const answer = u.id == targetUserId;
                if (answer) {
                    index = i;
                }
                return u.id == targetUserId;
            })[0];

            if (index >= 0) {
                user.loading = true;
                this.users.splice(index, 1, user);
            }
            this.isProcessing = true;

            $.post('/hsapi/_internal/' + this.resShortId + '/share-resource-with-' +
                (this.isInviteUsers ? 'user' : 'group') + '/' + this.selectedAccess + "/" +
                targetUserId + "/", function (result) {
                let resp;
                try {
                    resp = JSON.parse(result)
                }
                catch (error) {
                    console.log(error);
                    vue.error = "Failed to change permission";
                    vue.isProcessing = false;
                    return;
                }

                let index = -1;

                // Check if this user already has any access and get its index in the array
                for (let i = 0; i < vue.users.length; i++) {
                    if (vue.users[i].id === targetUserId) {
                        index = i;
                        break;
                    }
                }

                if (index >= 0) {
                    // An entry was found, update the data
                    let user = vue.users[index];
                    user.access = resp.privilege_granted;
                    user.loading = false;
                    vue.users.splice(index, 1, user);
                    if (vue.currentUser === user.id) {
                        vue.selfAccessLevel = user.access;
                    }
                }
                else {
                    // No entry found. Push new data

                    let pictureUrl;
                    if (vue.isInviteUsers) {
                        pictureUrl = resp.profile_pic === "None" ? null : resp.profile_pic;
                    }
                    else {
                        pictureUrl = resp.group_pic === "None" ? null : resp.group_pic;
                    }

                    const newUserAccess = {
                        user_type: vue.isInviteUsers ? 'user' : 'group',
                        access: resp.privilege_granted,
                        id: targetUserId,
                        pictureUrl: pictureUrl,
                        best_name: resp.name,
                        user_name: resp.username,
                        loading: false,
                        can_undo: true,
                    };

                    vue.users.push(newUserAccess);
                }

                vue.isProcessing = false;
            });
        },
        removeAccess: function (user, index) {
            user.loading = true;
            this.users.splice(index, 1, user);
            let vue = this;
            vue.error = "";
            this.isProcessing = true;

            $.post('/hsapi/_internal/' + this.resShortId + '/unshare-resource-with-' +
                user.user_type + '/' + user.id + '/', function (resp) {
                if (resp.status === "success") {
                    vue.users.splice(index, 1);
                    if (resp.hasOwnProperty('redirect_to')) {
                        window.location.href = resp.redirect_to;
                    }
                }
                else {
                    user.loading = false;
                    vue.users.splice(index, 1, user);
                    vue.error = resp.message;
                    vue.isProcessing = false;
                    console.log(resp);
                }
            });
        },
        setResourceAccess: function (action) {
            let vue = this;
            vue.isProcessingAccess = true;
            $.post('/hsapi/_internal/' + this.resShortId + '/set-resource-flag/',
                {flag: action, 'resource-mode': this.resourceMode}, function (resp) {
                    const resAccessStr = {
                        make_public: "Public",
                        make_discoverable: "Discoverable",
                        make_private: "Private"
                    };

                    if (resp.status === 'success') {
                        if (action === 'make_public') {
                            vue.resAccess = {
                                isPublic: true,
                                isDiscoverable: true,
                                isShareable: vue.resAccess.isShareable,
                            };
                        }
                        else if (action === 'make_discoverable') {
                            vue.resAccess = {
                                isPublic: false,
                                isDiscoverable: true,
                                isShareable: vue.resAccess.isShareable,
                            }
                        }
                        else if (action === 'make_private') {
                            vue.resAccess = {
                                isPublic: false,
                                isDiscoverable: false,
                                isShareable: vue.resAccess.isShareable,
                            }
                        }
                    }

                    vue.isProcessingAccess = false;
                }
            );
        },
        setShareable: function (action) {
            let vue = this;
            vue.isProcessingShareable = true;
            vue.sharingError = "";
            $.post('/hsapi/_internal/' + this.resShortId + '/set-resource-flag/',
                {flag: action, 'resource-mode': this.resourceMode}, function (resp) {
                    if (resp.status === "error") {
                        vue.sharingError = resp.message;
                    }
                    vue.isProcessingShareable = false;
                }
            );
        },
        setQuotaHolder: function (username) {
            let vue = this;
            vue.quotaError = "";

            $.post('/hsapi/_internal/' + this.resShortId + '/change-quota-holder/',
                {new_holder_username: username}, function (resp) {
                    if (resp.status === "success") {
                        var newHolder = vue.users.find(function(user) {
                            return user.user_name === username;
                        });

                        vue.quotaHolder = newHolder;
                    }
                    else {
                        vue.quotaError = resp.message;
                    }
                }
            );
        },
        onMetadataInsufficient: function () {
            // Set the resource access to private
            this.resAccess = {
                isPublic: false,
                isDiscoverable: false,
                isShareable: this.resAccess.isShareable,
            };
            // The metadata is insufficient
            this.canBePublicDiscoverable = false;
        }
    },
});