let leftHeaderApp = new Vue({
    el: '#left-header',
    delimiters: ['${', '}'],
    data: {
        owners: USERS_JSON.map(function(user) {
            user.loading = false;
            return user;
        }).filter(function(user){
            return user.access === 'owner';
        }),
        res_mode: RESOURCE_MODE,
        resShortId: SHORT_ID,
        can_change: CAN_CHANGE,
        authors: AUTHORS,
        selectedAuthor: {
            "id": null,
            "name": null,
            "email": null,
            "organization": null,
            "identifiers": {},
            "address": null,
            "phone": null,
            "homepage": null,
            "profileUrl": null
        },
        userCardSelected: {
            user_type: null,
            access: null,
            id: null,
            pictureUrl: null,
            best_name: null,
            user_name: null,
            can_undo: null,
            email: null,
            organization: null,
            title: null,
            contributions: null,
            subject_areas: null,
            identifiers: [],
            state: null,
            country: null,
            joined: null,
        },
        lastChanagedBy: LAST_CHANGED_BY,
        cardPosition: {
            top: 0,
            left: 0,
        }
    },
    methods: {
        onLoadOwnerCard: function(data) {
            let el = $(data.event.target);
            let cardWidth = 350;

            this.userCardSelected = data.user;
            this.cardPosition.left = el.position().left - (cardWidth / 2) + (el.width() / 2);
            this.cardPosition.top = el.position().top + 30;
        },
        deleteAuthor: function (author) {
            // TODO: change endpoint to return json data
            $.post('/hsapi/_internal/' + this.resShortId + '/creator/' + author.id +
                '/delete-metadata/', function (result) {
                console.log(result);
            });
        },
        updateAuthor: function(author) {

        },
        selectAuthor: function(author) {
            this.selectedAuthor = $.extend(true, {}, author);  // Deep copy
        }
    }
});