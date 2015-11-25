﻿(function ($) {
    'use strict';
    function Application() {
        this.content_posts_defer = $.Deferred();
        this.$window = $(window);
    }
    Application.prototype = {
        all_posts_content: {'length': 0},
        current_page: 1,
        all_page_loaded: false,
        group: '',
        group_id: '',
        startX: 0,
        startY: 0,
        endX: 0,
        endY: 0,
        posts_count: 0,
        max_mark: 50,
        is_gesture: false,
        $window: null,
        $current_post: null,
        $status_element: null,
        status_interval_handler: 0,
        $only_unread_checkbox: null,
        $post_links: null,
        post_links_id: -1,
        current_search_result: [],
        $search_field: null,
        $search_result_window: null,
        scroll_position: 0,
        $toolbar: null,
        $toolbar_bottom: null,
        $loading: null,
        current_posts_id: {},
        current_posts_id_length: 0,
        selected_tags: [],
        attempts_count: 0,
        max_attempts_count: 10,
        content_posts_defer: null,
        search_request_t_out: -1,
        urls: {
            'mark_read_posts_url': '/read/posts',
            'update_prev_next_link_url': '/tag/prev-next',
            'posts_content_url': '/posts-content',
            'post_content_url': '/post-content',
            'post_links_url': '/post-links',
            'ready_check_url': '/ready',
            'only_unread_url': '/only-unread',
            'all_tags_url': '/all-tags',
            'posts_with_tags_url': '/posts/with/tags',
            'search_tags_url': '/tags-search',
            'speech_url': '/speech'
        },
        all_showed: false,
        cloud_items_count: 0,

        checkStatus: function () {
            var defer = $.ajax({
                'url': this.urls.ready_check_url,
                'type': 'GET',
                'dataType': 'json',
                'async': true
            });
            return defer.promise();
        },

        processStatus: function (result) {
            var appl = this;
            if (result) {
                //result.status = 'not ready';
                switch (result.status) {
                    case 'ready': {
                        this.$status_element.attr('class', 'status_ready');
                        if (this.$loading.is(':visible')) {
                            /*this.$loading.hide();
                            $('.root_item').show();
                            $('#status').hide();*/
                            window.location = '/';
                        }
                        break;
                    }
                    case 'not ready': {
                        this.$status_element.attr('class', 'status_not_ready');
                        if (this.$loading.is(':hidden')) {
                            this.$loading.show();
                            $('.root_item').hide();
                            $('#status').show();
                        }
                        this.status_interval_handler = setTimeout(function () {
                            var promise = appl.checkStatus();
                            promise.done(function (check_result) {
                                appl.processStatus(check_result);
                            });
                        }, 5000);
                        break;
                    }
                    /*case 'not logged': {
                        //this.$status_element.attr('class', 'status_not_logged');
                        break;
                    }*/
                }
                this.$status_element.text(result.reason + '. ' + result.message);
            }
        },

        readOne: function (el_this) {
            var status_text = '',
                status = 0,
                promise = null,
                $this = $(el_this),
                app = this;
            if ($this.hasClass('read')) {
                status = 0;
                status_text = 'unread';
            } else {
                status = 1;
                status_text = 'read';
            }
            promise = $.ajax({
                url: app.urls.mark_read_posts_url,
                type: 'POST',
                data: {'pos': $this.data('pos'), 'status': status},
                dataType: 'json',
                async: true
            });
            promise.done(function (result) {
                if ((result !== undefined) && (result.result === 'ok')) {
                    $this.toggleClass('read unread')
                         .text(status_text);
                    //app.udpate_prev_next_links($('.page').data('tag'));
                } else {
                    alert('Error. Please try again later');
                }
                app.syncReadAllButton();
                app.repaintPostsStat();
            });
        },

        repaintPostsStat: function () {
            var unread = $('.unread').length,
                read = $('.read').length;
            $('#posts_stat').text('(' + unread + ' / ' + read + ')');
        },

        readAll: function (el_this) {
            var $this = $(el_this),
                app = this,
                promise = null,
                posts = [],
                $posts = $('div.post'),
                status = 0,
                confirmed = true,
                i;
            if ($posts.length === 0) {
                return;
            }
            if ($this.text() === 'read all') {
                status = 1;
            } else {
                status = 0;
            }
            if (($posts.length > 0) && ((this.max_mark < $posts.length) || (status === 0))) {
                confirmed = confirm($this.text() + ' ' + $posts.length + ' posts?');
            }
            if (confirmed) {
                for (i = 0; i < $posts.length; i++) {
                    posts.push($($posts[i]).data('pos'));
                }
                promise = $.ajax({
                    url: app.urls.mark_read_posts_url,
                    type: 'POST',
                    data: {'posts': posts, 'status': status},
                    dataType: 'json',
                    async: true
                });
                promise.done(function (result) {
                    if ((result !== undefined) && (result.result === 'ok')) {
                        $('span.read_button').each(function () {
                            var $this = $(this);
                            if (status === 1) {
                                $this.toggleClass('read unread')
                                     .text('read');
                            } else {
                                $this.toggleClass('read unread')
                                     .text('unread');
                            }
                        });
                        if (status === 1) {
                            $this.children('span').text('unread all');
                        } else {
                            $this.children('span').text('read all');
                        }
                        //app.udpate_prev_next_links($('.page').data('tag'));
                        app.repaintPostsStat();
                    } else {
                        alert('Error. Please try again later');
                    }
                });
            }
        },

        syncReadAllButton: function () {
            if ($('span.unread').length === 0) {
                $('#read_all').children('span').text('unread all');
            } else {
                $('#read_all').children('span').text('read all');
            }
        },

        showContent: function (el, show_status) {
            var $content = $(el).parent().children('.post_content'),
                pos = $content.parent().data('pos'),
                all_ready = new $.Deferred(),
                app = this,
                promise;
            all_ready.done(function () {
                $content.toggleClass('show hide');
                app.scrollTop(app.$current_post);
            });
            if (show_status === undefined) {
                if ($content.attr('class') === 'show') {
                    show_status = false;
                } else {
                    show_status = true;
                }
            }
            if (show_status) {
                if (app.all_posts_content[pos] === undefined) {
                    promise = app.loadPostContent(pos);
                    promise.done(function () {
                        //$content.attr('class', 'show');
                        $content.html(app.all_posts_content[pos])
                                .find('img').removeAttr('height');
                        all_ready.resolve();
                    });
                } else {
                    //$content.attr('class', 'show');
                    $content.html(app.all_posts_content[pos])
                            .find('img').removeAttr('height');
                    all_ready.resolve();
                }
            } else {
                //$content.attr('class', 'hide');
                $content.text('');
                all_ready.resolve();
            }
            return all_ready;
        },

        showAll: function (el_this) {
            var $this = $(el_this),
                app = this,
                all_ready = $.Deferred(),
                show_status = false;
            this.collectCurrentPostsID();
            if (this.all_showed) {
                show_status = false;
                $this.children('span').text('show all');
                all_ready.resolve();
            } else {
                if (this.all_page_loaded) {
                    show_status = true;
                    $this.children('span').text('hide all');
                    all_ready.resolve();
                } else {
                    this.loadPostsContent();
                    this.content_posts_defer.done(function () {
                        show_status = true;
                        $this.children('span').text('hide all');
                        all_ready.resolve();
                    });
                }
            }
            all_ready.done(function () {
                $('div.post_content').each(function () {
                    app.showContent(this, show_status);
                });
                app.all_showed = !app.all_showed;
            });
        },

        /*udpate_prev_next_links: function (tag) {
            links = $.ajax({
                url: app.urls.update_prev_next_link_url + '?tag=' + tag,
                type: 'GET',
                dataType: 'json',
                async: false
            }).responseJSON;
            if (links) {
                $('#next_tag').children('a').attr('href', links.next);
                $('#prev_tag').children('a').attr('href', links.prev);
            }
        },*/

        loadPostContent: function (pos) {
            var app = this,
                promise = $.ajax({
                    url: app.urls.post_content_url,
                    type: 'POST',
                    data: {'postid': pos},
                    dataType: 'json',
                    async: true
                });
            promise.done(function (content) {
                if ((content) && (content.result === 'ok')) {
                    app.all_posts_content[content.data.pos] = content.data.content;
                    app.all_posts_content.length++;
                    if (!app.all_page_loaded) {
                        if (app.all_posts_content.length >= app.posts_count) {
                            app.all_page_loaded = true;
                        }
                    }
                } else {
                    alert('error');
                }
            });
            return promise;
        },

        collectCurrentPostsID: function () {
            var appl = this,
                pos;
            this.current_posts_id = {};
            this.current_posts_id_length = 0;
            $('.post').each(function () {
                pos = $(this).data('pos');
                appl.current_posts_id[pos] = pos;
                appl.current_posts_id_length++;
            });
        },

        getCurrentPostsIDArray: function () {
            var arr = [],
                pos;
            for (pos in this.current_posts_id) {
                if (this.current_posts_id.hasOwnProperty(pos)) {
                    arr.push(pos);
                }
            }
            return arr;
        },

        loadPostsContent: function () {
            var app = this,
                defer,
                ps;
            this.attempts_count++;
            if (!app.all_page_loaded) {
                ps = app.getCurrentPostsIDArray();
                defer = $.ajax({
                    url: app.urls.posts_content_url,
                    type: 'POST',
                    data: {'posts': ps},
                    dataType: 'json',
                    async: true
                });
                defer.done(function (content) {
                    var pos,
                        i;
                    if ((content) && (content.result === 'ok')) {
                        for (i = 0; i < content.data.length; i++) {
                            pos = content.data[i].pos;
                            app.all_posts_content[pos] = content.data[i].content;
                            if ((app) && (app.current_posts_id) && (pos in app.current_posts_id)) {
                                delete app.current_posts_id[pos];
                                app.current_posts_id_length--;
                            }
                        }
                        if ((app.current_posts_id_length <= 0) || (app.attempts_count > app.max_attempts_count)) {
                            app.all_page_loaded = true;
                            app.attempts_count = 0;
                            app.content_posts_defer.resolve();
                        }
                    } else {
                        alert('Error. Please try later');
                        app.all_page_loaded = true;
                        app.attempts_count = 0;
                    }
                    if (!app.all_page_loaded) {
                        app.loadPostsContent();
                    }
                });
            }
        },

        setCurrentPost: function (current_post) {
            var $cp = $(current_post);
            if ($cp.data('pos') !== this.$current_post.data('pos')) {
                this.$current_post.removeClass('current_post');
                this.$current_post = $cp;
                this.$current_post.addClass('current_post');
            }
        },

        scrollTop: function (el) {
            window.scrollTo(0, $(el).offset().top - (this.$toolbar.height() * 2));
        },

        scrollUp: function (position) {
            this.scroll_position = position ? position : 0;
            this.showToolbar();
        },

        scrollDown: function (position) {
            this.scroll_position = position ? position : 0;
            this.hideToolbar();
        },

        showToolbar: function () {
            this.$toolbar.show();
            this.$toolbar_bottom.show();
        },

        hideToolbar: function () {
            this.$toolbar.hide();
            this.$toolbar_bottom.hide();
        },

        setOnlyUnread: function () {
            var app = this,
                promise,
                status;
            if (app.$only_unread_checkbox.prop('checked')) {
                status = 1;
            } else {
                status = 0;
            }
            promise = $.ajax({
                url: app.urls.only_unread_url,
                type: 'POST',
                data: {'status': status},
                dataType: 'json',
                async: true
            });
            promise.done(function (content) {
                if ((content) && (content.result === 'ok')) {
                    app.$only_unread_checkbox.val(true);
                    if (window.location.pathname !== '/') {
                        window.location.reload();
                    }
                } else {
                    app.$only_unread_checkbox.prop('checked', !app.$only_unread_checkbox.prop('checked'));
                    alert('error');
                }
            });
        },
        showHelp: function () {
            var $help = $('#help_window');
            if ($help) {
                if ($help.css('display') === 'none') {
                    $help.show();
                } else {
                    $help.hide();
                }
            }
        },
        hideHelp: function () {
            $('#help_window').hide();
        },
        showTags: function () {
            var app = this,
                l_found = false,
                c_found = false,
                b_found = false,
                defer;
            defer = $.ajax({
                type: 'GET',
                url: $('#link_to_back').children('a').attr('href'),
                dataType: 'html',
                async: true
            });
            defer.done(function (html) {
                var el_array = $.parseHTML(html, undefined, false),
                    i;
                for (i = 0; i < el_array.length; i++) {
                    if ((!l_found) && (el_array[i].id === 'letters')) {
                        $('.page').append(el_array[i]);
                        l_found = true;
                    } else if ((!c_found) && (el_array[i].className === 'page')) {
                        $('.page').append(el_array[i].childNodes);
                        c_found = true;
                    } else if ((!b_found) && (el_array[i].id === 'global_tools_bottom')) {
                        $('body').append(el_array[i]);
                        b_found = true;
                    }
                }
            }).fail(function () {
                alert('Error. Try later.');
            });/*.always(function() {
                app.scrollTop(this);
                $(this).hide();
            });*/
        },
        groupByCategory: function () {
            $('li.category').children('.show_btn').click(function () {
                var $this = $(this);
                $this.toggleClass('minimized not_minimized');
                $this.parent().children('.feeds').toggleClass('hidden not_hidden');
            });
        },
        searchTags: function () {
            var req = this.last_search_request,
                app = this,
                defer;
            defer = $.ajax({
                url: this.urls.search_tags_url,
                type: 'POST',
                data: {
                    'req': encodeURIComponent(req)
                },
                datatType: 'json',
                async: true
            });
            defer.done(function (data) {
                if (data.result === 'ok') {
                    app.current_search_result = data.data;
                    app.showSearchResult();
                } else {
                    alert(data.data);
                }
            }).fail(function () {
                alert('Error. Try later');
            });
        },
        showSearchResult: function () {
            var result_len = this.current_search_result.length,
                items = [],
                p_item,
                a_item,
                i,
                p,
                a;
            this.$search_result_window.empty();
            if (result_len > 0) {
                p = document.createElement('p');
                p.className = 'search_result_item';
                a = document.createElement('a');
                for (i = 0; i < result_len; i++) {
                    p_item = p.cloneNode();
                    a_item = a.cloneNode();
                    a_item.setAttribute('href', this.current_search_result[i].url);
                    a_item.textContent = decodeURIComponent(this.current_search_result[i].tag) + ' (' + this.current_search_result[i].cnt + ')';
                    p_item.appendChild(a_item);
                    items.push(p_item);
                }
                this.$search_result_window.append(items)
                    .show();
            } else {
                this.$search_result_window.hide();
            }
        },
        showPostLinks: function (el_this) {
            var $this = $(el_this),
                app = this,
                postid = $this.parent().parent().data('pos'),
                p_l = '',
                promise;
            if (app.post_links_id !== postid) {
                promise = $.ajax({type: 'POST', data: {'postid': postid}, url: app.urls.post_links_url, dataType: 'json', async: true});
                promise.done(function (result) {
                    var offset,
                        data,
                        i;
                    if ((result) && (result.result === 'ok')) {
                            data = result.data;
                        p_l = '<a href="' + data.c_url + '">' + data.c_title +
                            '</a> | <a href="' + data.f_url + '">' + data.f_title + '</a>' +
                            '</a> | <a href="' + data.p_url + '">To site</a><br />';
                        //var d_length = data.tags.length;
                        for (i = 0; i < data.tags.length; i++) {
                            p_l += '<a href="' + data.tags[i].url + '">' + data.tags[i].tag + '</a>, ';
                        }
                        app.post_links_id = postid;
                        $this.parent().find('.post_links_content').html(p_l);
                    } else {
                        alert(result.data);
                    }
                });
            }
            return false;
        },
        processSelectedTags: function ($el) {
            var result;
            if ($el.hasClass('selected_tag')) {
                //$el.removeClass('selected_tag');
                //delete(this.selected_tags[0]);
                this.selected_tags = [];
                result = false;
            } else {
                //$el.addClass('selected_tag');
                this.selected_tags.push($el);
                result = true;
            }
            $el.toggleClass('selected_tag');
            return result;
        },
        processTagSelection: function (el) {
            var $el = $(el),
                tags = [],
                $first_tag,
                $second_tag,
                second_tag = '',
                result = false,
                e_tags = '';
            if (this.processSelectedTags($el)) {
                if (this.selected_tags.length === 2) {
                    if (this.selected_tags[0].nextAll('.selected_tag').length > 0) {
                        $first_tag = this.selected_tags[0];
                        $second_tag = this.selected_tags[1];
                    } else {
                        $first_tag = this.selected_tags[1];
                        $second_tag = this.selected_tags[0];
                    }
                    tags.push($first_tag.find('.cloud_item_title').text());
                    second_tag = $second_tag.find('.cloud_item_title').text();
                    $first_tag.nextAll().each(function () {
                        var tag = $(this).find('.cloud_item_title').text(),
                            go_on = true;
                        tags.push(tag);
                        if (tag === second_tag) {
                            go_on = false;
                        }
                        return go_on;
                    });
                    $first_tag.removeClass('selected_tag');
                    $second_tag.removeClass('selected_tag');
                    this.selected_tags = [];
                    e_tags = encodeURIComponent(tags.join('-'));
                    window.location = this.urls.posts_with_tags_url + '/' + e_tags;
                }
            }
            return result;
        },
        processScroll: function () {
            var app = this;
            this.scroll_position = this.$window.scrollTop();
            this.$window.on('scroll', function () {
                var sc_t = app.$window.scrollTop();
                if (app.scroll_position >= sc_t) {
                    app.scrollUp(sc_t);
                } else {
                    app.scrollDown(sc_t);
                }
            });
        },
        processMainMenu: function () {
            var appl = this;
            $('.main_menu_button').on('click', function () {
                var offset,
                    $this = $(this),
                    $menu_window = $('.main_menu_window');
                if ($menu_window.css('display') === 'none') {
                    offset = $this.offset();
                    $menu_window.css({
                        top: offset.top + $this.height(),
                        right: appl.$window.width() - offset.left
                    });
                    $menu_window.show();
                } else {
                    $menu_window.hide();
                }
            });
        },
        showProgressbar: function () {
            this.$loading.show();
        },
        hideProgressbar: function () {
            this.$loading.hide();
        },
        toSpeech(): function() {
            var app = this,
                post_id = this.$current_post.data('pos'),
                $defer;

            $defer = $.ajax({
                'url': this.urls.speech_url,
                'data': post_id,
                'type': 'POST',
                'dataType': 'json',
                'async': true
            });

            $defer.done(function(data) {
                if (data.result && data.result === 'ok') {
                    app.$player.src = data.data;
                } else {
                    alert(data.reason);
                }
            }).fail(function(data) {
                console.log(data);
                alert('Something wrong');
            });
            return $defer.promise();
        }
    };

    $(document).on('ready', function () {
        var app = new Application(),
            $help_button,
            status_promise,
            $letters_array,
            e_alpha_reg,
            c_alpha_reg,
            prev_letter,
            $div_posts,
            reg_num,
            $letters,
            nums_reg,
            $cloud,
            regs,
            path,
            i;
        app.processScroll();
        if ($('#only_unread_checkbox').length > 0) {
            app.$only_unread_checkbox = $('#only_unread_checkbox');
            app.$only_unread_checkbox.click(function () {
                app.setOnlyUnread();
            });
        }
        $help_button = $('#help_button');
        if ($help_button.length > 0) {
            $help_button.on('focusout', function () {
                app.hideHelp();
            });
            $help_button.on('click', function () {
                app.showHelp(this);
            });
            $(document).on('keydown', function (e) {
                //var event = e || window.event;
                var key = e.which; //e.keyCode || e.charCode;
                if (key === 27) {
                    app.hideHelp();
                }
            });
        }
        app.$loading = $('#loading');
        path = window.location.pathname;
        app.$toolbar = $('#global_tools');
        app.$toolbar_bottom = $('#global_tools_bottom');
        app.processMainMenu();
        if (path === '/') {
            app.$status_element = $('#status').children('span');
            $('.page').css('margin-top', app.$toolbar.height());
            //app.status_interval_handler = setInterval(function () {app.checkStatus();}, 5000);
            status_promise = app.checkStatus();
            status_promise.done(function (result) {
                app.processStatus(result);
            });
        } else if (path === '\/group\/category') {
            app.groupByCategory();
        } else if (/\/group\/tag\/.*/.test(path)) {
            $(document).ajaxStart(function () {
                app.showProgressbar();
            }).ajaxStop(function () {
                app.hideProgressbar();
            });
            $cloud = $('.cloud');
            $cloud.on('click', '.cloud_item', function () {
                app.processTagSelection(this);
            });
            app.$search_field = $('.search_field');
            app.$search_result_window = $('.search_result');
            app.$search_field.on('keyup', function () {
                var req = '';
                if (app.search_request_t_out !== -1) {
                    app.$search_result_window.hide();
                    clearTimeout(app.search_request_t_out);
                }
                req = app.$search_field.val().toLowerCase();
                if ((req !== '') && (app.last_search_request !== req)) {
                    app.last_search_request = req;
                    app.search_request_t_out = setTimeout(function () {
                        app.search_request_t_out = -1;
                        app.searchTags();
                    }, 500);
                }
            });
            regs = [];
            reg_num = 0;
            $letters = $('.letters').find('.letter');
            prev_letter = $letters.eq(0).text();
            $letters.eq(0).parent().css('margin-top', app.$toolbar.height());
            $letters_array = [];
            nums_reg = /[0-9]/;
            e_alpha_reg = /[a-zA-Z]/;
            c_alpha_reg = /[а-яА-ЯёЁ]/;
            $letters.each(function () {
                var $this = $(this),
                    letter = $this.text();
                $letters_array.push({'$el': $this, 'l': letter});
                if (nums_reg.test(letter)) {
                    regs.push(nums_reg);
                    nums_reg = /^$/;
                } else if (e_alpha_reg.test(letter)) {
                    regs.push(e_alpha_reg);
                    e_alpha_reg = /^$/;
                } else if (c_alpha_reg.test(letter)) {
                    regs.push(c_alpha_reg);
                    c_alpha_reg = /^$/;
                }
            });
            for (i = 0; i < $letters_array.length; i++) {
                if (regs[reg_num].test(prev_letter) && !regs[reg_num].test($letters_array[i].l)) {
                    $letters_array[i].$el.before(document.createElement('br'));
                    prev_letter = $letters_array[i].l;
                    reg_num++;
                }
            }
        } else if (/^\/feed*/.test(path) || /^\/category*/.test(path) || /^\/tag/.test(path) || /^\/posts\/with\/tags\/.*/.test(path)) {
            $(document).ajaxStart(function () {
                app.showProgressbar();
            }).ajaxStop(function () {
                app.hideProgressbar();
            });

            $div_posts = $('div.post');
            app.$current_post = $div_posts.eq(0);//$('.post').eq(0);
            app.$current_post.addClass('current_post');
            app.posts_count = $div_posts.length;
            $('.page').css('margin-top', app.$toolbar.height());
            //$('#posts_count').text(app.posts_count);
            app.repaintPostsStat();
            $div_posts.click(function () {
                app.setCurrentPost(this);
            });
            $div_posts.on('touchstart', function (e) {
                var touch = e.originalEvent.changedTouches[0];
                app.startX = touch.pageX;
                app.startY = touch.pageY;
            });
            $div_posts.on('touchmove', function () {
                app.is_gesture = true;
            });
            $div_posts.on('touchend', function (e) {
                var touch = e.originalEvent.changedTouches[0],
                    lineX,
                    lineY;
                app.endX = touch.pageX;
                app.endY = touch.pageY;
                if (app.is_gesture) {
                    lineX = Math.abs(app.startX - app.endX);
                    lineY = Math.abs(app.startY - app.endY);
                    if ((lineX > 150) && (lineY < 20)) {
                        app.setCurrentPost(this);
                        app.showContent($(this).children('.post_content'));
                    }
                }
            });
            $div_posts.on('touchcancel', function (e) {
                var touch = e.originalEvent.changedTouches[0],
                    lineX,
                    lineY;
                app.endX = touch.pageX;
                app.endY = touch.pageY;
                if (app.is_gesture) {
                    lineX = Math.abs(app.startX - app.endX);
                    lineY = Math.abs(app.startY - app.endY);
                    if ((lineX > 15) && (lineY < 5)) {
                        app.setCurrentPost(this);
                        app.showContent($(this).children('.post_content'));
                    }
                }
            });
            app.group = $('.page').data('group');
            switch (app.group) {
                case 'feed': {
                    app.group_id = $('.post').data('feed');
                    break;
                }
                case 'category': {
                    app.group_id = $('.page').data('tag');
                    break;
                }
                case 'tag': {
                    $('.page').each(function () {
                        app.group_id += $(this).data('tag') + ',';
                    });
                    break;
                }
            }
            app.current_page = 1;
            app.syncReadAllButton();
            $('a.post_show_links').on('click', function () {
                app.showPostLinks(this);
                return false;
            });
            $('.post_links_close').on('click', function () {
                $(this).parent().hide();
            });
            $('span.read_button').on('click', function () {
                app.readOne(this);
            });
            $('#read_all').click(function () {
                app.readAll(this);
            });
            $('a.post_show_content').on('click', function () {
                var $prnt = $(this).parent();
                app.setCurrentPost($prnt.parent());
                app.showContent($prnt);
                return false;
            });
            $('.post_title_link').on('mouseup', function (e) {
                var key = e.which,
                    self;
                if ((key === 1) || (key === 2)) {
                    self = $(this).parent().parent().find('.read_button');
                    if (self.hasClass('unread')) {
                        setTimeout(function () {self.click();}, 50);
                    }
                }
            });
            $('#show_all').on('click', function () {
                app.showAll(this);
            });
            app.cloud_items_count = $('li.cloud_item').length;
            if (app.cloud_items_count !== 0) {
                $('#cloud_items_count').text(app.cloud_items_count);
            }
            $(document).on('keydown', function (e) {
                //var event = e || window.event;
                var key = e.which, //e.keyCode || e.charCode;
                    nexts,
                    prevs;
                switch (key) {
                    case 65: {
                        if (e.shiftKey) {//shift-a
                            $('#read_all').click();
                        }
                        break;
                    }
                    case 83: {
                        if (e.shiftKey) {//shift-s
                            /*$div_posts.each(function () {
                                app.showContent($(this).children('.post_content'));
                            });*/
                            $('#show_all').click();
                        } else {
                            app.showContent(app.$current_post.children('.post_content'));
                        }
                        break;
                    }
                    case 77: {//m
                        app.$current_post.find('.read_button').click();
                        break;
                    }
                    case 78: {//n
                        nexts = app.$current_post.next('.post');
                        if (nexts.length > 0) {
                            app.setCurrentPost(nexts[0]);
                            app.scrollTop(app.$current_post);
                        }
                        break;
                    }
                    case 66: {//b
                        prevs = app.$current_post.prev('.post');
                        if (prevs.length > 0) {
                            app.setCurrentPost(prevs[0]);
                            app.scrollTop(app.$current_post);
                        }
                        break;
                    }
                    case 74: {//j
                        break;
                    }
                    case 75: {//k
                        break;
                    }
                    case 72: {//h
                        $('#help_button').click();
                        break;
                    }
                    case 86: {
                        app.toSpeech();
                        break
                    }
                    case 38: {
                        if (e.ctrlKey) {//ctrl-up
                            window.location = $('#link_to_back').children('a').attr('href');
                        }
                        break;
                    }
                    case 40: {
                        if (e.ctrlKey) {//ctrl-down
                            $('#show_tags').click();
                            if ($('li.category').length > 0) {
                                app.groupByCategory();
                            }
                        }
                        break;
                    }
                    /*case 27: {
                    }*/
                }
            });
            /*$(document).scroll(function () { //not async version, need change
                if (!app.all_page_loaded) {

                    //app.loadPostsContent();
                }
            });*/
            //$('#show_tags').click(app.showTags);
        }
    });
})(jQuery);
