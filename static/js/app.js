(function($){

app = {
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
is_gesture: false,
$current_post: undefined,
$status_element: undefined,
status_interval_handler: 0,
$only_unread_checkbox: undefined,
$post_links: undefined,
post_links_id: -1,
all_tags: null,
tags_index: null,
current_search_result: [],
$search_field: null,
$search_result_window: null,
scroll_position: 0,
$toolbar: undefined,
urls: {
    'mark_read_posts_url': '/read/posts',
    'update_prev_next_link_url': '/tag/prev-next',
    'posts_content_url': '/posts-content',
    'post_content_url': '/post-content',
    'post_links_url': '/post-links',
    'ready_check_url': '/ready',
    'only_unread_url': '/only-unread',
    'all_tags_url': '/all-tags',
},
all_showed: false,
cloud_items_count: 0,

checkStatus: function() {
    result = $.ajax({
        'url': app.urls['ready_check_url'],
        'type': 'GET',
        'dataType': 'json',
        'async': false,
    }).responseJSON;
    if (result) {
        switch (result['status']) {
            case 'ready': {
                clearInterval(app.status_interval_handler);
                app.$status_element.attr('class', 'status_ready');
                break;
            }
            case 'not ready': {
                app.$status_element.attr('class', 'status_not_ready');
                break;
            }
            case 'not logged': {
                clearInterval(app.status_interval_handler);
                app.$status_element.attr('class', 'status_not_logged');
                break;
            }
        }
        app.$status_element.text(result['reason'] + '. ' + result['message']);
    }
},

readOne: function(el_this) {
    var status_text = '';
    var status = 0;
    var promise = null;
    var $this = $(el_this);
    var app = this;
    if ($this.hasClass('read')) {
        status = 0;
        status_text = 'unread';
    }
    else {
        status = 1;
        status_text = 'read';
    }
    promise = $.ajax({
        url: app.urls['mark_read_posts_url'],
        type: 'POST',
        data: {'pos' : $this.data('pos'), 'status': status},
        dataType: 'json',
        async: true
    });
    promise.done(function(result){
        if ((result != undefined) && (result['result'] == 'ok')) {
            $this.toggleClass('read unread')
                 .text(status_text);
            //app.udpate_prev_next_links($('.page').data('tag'));
        }
        else {
            alert('Error. Please try again later');
        }
        app.syncReadAllButton();
    });
},

readAll: function(el_this) {
    var $this = $(el_this);
    var app = this;
    var promise = null;
    var posts = Array();
    var $posts = $('div.post');
    var status = 0;
    if ($this.text() == 'read all') {
        status = 1;
    }
    else {
        status = 0;
    }
    for (i = 0; i < $posts.length; i++) {
        posts.push($($posts[i]).data('pos'));
    }
    promise = $.ajax({
        url: app.urls['mark_read_posts_url'],
        type: 'POST',
        data: {'posts': posts, 'status': status},
        dataType: 'json',
        async: true
    });
    promise.done(function(result) {
        if ((result != undefined) && (result['result'] == 'ok')) {
            $('span.read_button').each(function() {
                var $this = $(this);
                if (status == 1) {
                    $this.toggleClass('read unread')
                         .text('read');
                }
                else {
                    $this.toggleClass('read unread')
                         .text('unread');
                }
            });
            if (status == 1) {
                $this.children('span').text('unread all');
            }
            else {
                $this.children('span').text('read all');
            }
            //app.udpate_prev_next_links($('.page').data('tag'));
        }
        else {
            alert('Error. Please try again later');
        }
    });
},

syncReadAllButton: function() {
    if ($('span.unread').length == 0) {
        $('#read_all').children('span').text('unread all');
    }
    else {
        $('#read_all').children('span').text('read all');
    }
},

showContent: function(el, show_status) {
    var $content = $(el).parent().children(".post_content");
    var pos = $content.parent().data('pos');
    var app = this;
    var all_ready = $.Deferred();
    all_ready.done(function(){
        $content.toggleClass('show hide');
        app.scrollTop(app.$current_post);
    });
    if (show_status == undefined) {
        if ($content.attr('class') == 'show') {
            show_status = false;
        }
        else {
            show_status = true;
        }
    }
    if (show_status) {
        if (!app.all_posts_content[pos]) {
            var promise = app.loadPostContent(pos);
            promise.done(function(){
                //$content.attr('class', 'show');
                $content.html(app.all_posts_content[pos]);
                all_ready.resolve();
            });
        }
        else {
            //$content.attr('class', 'show');
            $content.html(app.all_posts_content[pos]);
            all_ready.resolve();
        }
    }
    else {
        //$content.attr('class', 'hide');
        $content.text('');
        all_ready.resolve();
    }
    return(all_ready);

},

showAll: function(el_this) {
    var $this = $(el_this);
    var app = this;
    var all_ready = $.Deferred();
    var show_status = false;
    all_ready.done(function(){
        $('div.post_content').each(function(){
            app.showContent(this, show_status);
        });
        app.all_showed = !app.all_showed;
    });
    if (app.all_showed) {
        show_status = false;
        $this.children('span').text('show all');
        all_ready.resolve();
    }
    else {
        if (app.all_page_loaded) {
            show_status = true;
            $this.children('span').text('hide all');
            all_ready.resolve();
        }
        else {
            var promise = app.loadPostsContent();
            promise.done(function() {
                show_status = true;
                $this.children('span').text('hide all');
                all_ready.resolve();
            });
        }
    }

},

/*udpate_prev_next_links: function(tag) {
    links = $.ajax({
        url: app.urls['update_prev_next_link_url'] + '?tag=' + tag,
        type: 'GET',
        dataType: 'json',
        async: false
    }).responseJSON;
    if (links) {
        $('#next_tag').children('a').attr('href', links['next']);
        $('#prev_tag').children('a').attr('href', links['prev']);
    }
},*/

loadPostContent: function(pos) {
    var app = this;
    var promise = $.ajax({
        url: app.urls['post_content_url'],
        type: 'POST',
        data: {'postid': pos},
        dataType: 'json',
        async: true
    });
    promise.done(function(content) {
        if ((content) && (content['result'] == 'ok')) {
            app.all_posts_content[content['data']['pos']] = content['data']['content'];
            app.all_posts_content['length']++;
            if (!app.all_page_loaded) {
                if (app.all_posts_content['length'] >= app.posts_count) {
                    app.all_page_loaded = true;
                }
            }
        }
        else {
            alert('error');
        }
    });
    return(promise);
},

loadPostsContent: function() {
    /*content = $.ajax({
        url: app.urls['posts_content_url'],
        type: 'POST',
        data: {'group': app.group, 'group_id': app.group_id, 'page': app.current_page},
        dataType: 'json',
        //success: function(data){alert(data['result']);},
        //error: function(data){alert(data['result']);},
        async: false,
    }).responseJSON;
    if ((content) && (content['result'] == 'ok')) {
        for (i = 0; i < content['data'].length; i++) {
            app.all_posts_content[content['data'][i]['pos']] = content['data'][i]['content'];
        }
        if (content['page_count'] == app.current_page) {
            app.all_page_loaded = true;
        }
    }
    else {
        alert('error');
    }*/
    var app = this;
    if (!app.all_page_loaded) {
        var promise = $.ajax({
            url: app.urls['posts_content_url'],
            type: 'POST',
            data: {'group': app.group, 'group_id': app.group_id, 'page': app.current_page},
            dataType: 'json',
            async: true
        });
        promise.done(function(content){
            if ((content) && (content['result'] == 'ok')) {
                for (i = 0; i < content['data'].length; i++) {
                    app.all_posts_content[content['data'][i]['pos']] = content['data'][i]['content'];
                }
                app.all_posts_content['length'] = content['data'].length;
                if (content['page_count'] <= app.current_page) {
                    app.all_page_loaded = true;
                }
                else {
                    app.current_page++;
                }
            }
            else {
                alert('Error. Please try later');
                app.all_page_loaded = true
            }
            if (!app.all_page_loaded) {
                promise = app.loadPostsContent();
            }
        });
    }
    return(promise);
},

setCurrentPost: function(current_post) {
    $cp = $(current_post);
    if ($cp.data('pos') != app.$current_post.data('pos')) {
        app.$current_post.removeClass('current_post');
        app.$current_post = $cp;
        app.$current_post.addClass('current_post');
    }
},

scrollTop: function(el) {
    window.scrollTo(0, $(el).offset().top - ($('#global_tools').height() * 2));
},

scrollUp: function(position) {
    this.scroll_position = (position)? position: 0;
    this.showToolbar();
},

scrollDown: function(position) {
    this.scroll_position = (position)? position: 0;
    this.hideToolbar();
},

showToolbar: function() {
    this.$toolbar.show();
},

hideToolbar: function() {
    this.$toolbar.hide();
},

setOnlyUnread: function(el_this) {
    var app = this;
    if (app.$only_unread_checkbox.prop('checked')) {
        status = 1;
    }
    else {
        status = 0;
    }
    var promise = $.ajax({
        url: app.urls['only_unread_url'],
        type: 'POST',
        data: {'status': status},
        dataType: 'json',
        async: true,
    });
    promise.done(function(content){
        if ((content) && (content['result'] == 'ok')) {
            app.$only_unread_checkbox.val(true);
            if (window.location.pathname != '/') {
                window.location.reload();
            }
        }
        else {
            app.$only_unread_checkbox.prop('checked', !app.$only_unread_checkbox.prop('checked'));
            alert('error');
        }
    });
},
showHelp: function(el_this) {
    var $help = $('#help_window');
    if ($help) {
        if ($help.css('display') === 'none') {
            $help.show();
        }
        else {
            $help.hide();
        }
    }
},
showTags: function() {
    var app = this;
    var el_array = $.parseHTML($.ajax({type: 'GET', url: $('#link_to_back').children('a').attr('href'), dataType: 'html', async: false}).responseText, undefined, false);
    var l_found = false;
    var c_found = false;
    var b_found = false;
    for (var i = 0; i < el_array.length; i++) {
        if ((!l_found) && (el_array[i].id == 'letters')) {
            $('.page').append(el_array[i]);
            l_found = true;
        }
        else if ((!c_found) && (el_array[i].className == 'page')) {
            $('.page').append(el_array[i].childNodes);
            c_found = true;
        }
        else if ((!b_found) && (el_array[i].id == 'global_tools_bottom')) {
            $('body').append(el_array[i]);
            b_found = true;
        }
    }
    app.scrollTop(this);
    $(this).hide();
},
groupByCategory: function() {
    $('li.category').children('.show_btn').click(function() {
        $this = $(this);
        $this.toggleClass('minimized not_minimized');
        $this.parent().children('.feeds').toggleClass('hidden not_hidden');
    });
},
loadAllTags: function(callback) {
    $.ajax({url: this.urls['all_tags_url'], type: 'GET', dataType: 'json', success: callback});
},
buildTagsIndex: function() {
    this.tags_index = {};
    var all_tags_len = this.all_tags.length;
    for (var j = 0; j < all_tags_len; j++) {
        var current_tag = this.all_tags[j].t;
        var tag_len = current_tag.length;
        var indx = '';
        for (var i = 0; i < tag_len; i++) {
            indx = current_tag.charAt(i) + i;
            if (this.tags_index[indx]) {
                this.tags_index[indx].push(j);
            }
            else {
                this.tags_index[indx] = [j];
            }
        }
    }
},
searchTag: function() {
    var req = this.$search_field.val();
    this.current_search_result = [];
    var tmp_result = [];
    if (req) {
        req_len = req.length;
        var indx = req.charAt(0) + 0;
        if (this.tags_index[indx]) {
            tmp_result = this.tags_index[indx].slice(0);
            for (var i = 1; i < req_len; i++) {
                indx = req.charAt(i) + i;
                if (this.tags_index[indx]) {
                    if (tmp_result) {
                        var new_tmp_result = []
                        var tmp_len = tmp_result.length;
                        var tmp_arr = this.tags_index[indx].slice(0);
                        var tmp_arr_len = tmp_arr.length;
                        for (var j = 0; j < tmp_len; j++) {
                            for (z = 0; z < tmp_arr_len; z++) {
                                if (tmp_result[j] == tmp_arr[z]) {
                                    new_tmp_result.push(tmp_result[j])
                                    //tmp_arr[z].t = '';
                                    break;
                                }
                            }
                        }
                        tmp_result = new_tmp_result.slice(0);
                    }
                    else {
                        break;
                    }
                }
            }
            this.current_search_result = tmp_result.slice(0);
        }
    }
},
showSearchResult: function() {
    this.$search_result_window.empty();
    var result_len = this.current_search_result.length;
    if (result_len > 0) {
        var p = document.createElement('p');
        p.className = 'search_result_item';
        var a = document.createElement('a');
        var items = [];
        for (var i = 0; i < result_len; i++) {
            var ii = this.current_search_result[i];
            p_item = p.cloneNode();
            a_item = a.cloneNode();
            a_item.setAttribute('href', this.all_tags[ii].l);
            a_item.textContent = this.all_tags[ii].t;
            p_item.appendChild(a_item);
            items.push(p_item);
        }
        this.$search_result_window.append(items)
                                  .show();
    }
    else {
        this.$search_result_window.hide();
    }
},
showPostLinks: function(el_this) {
    var $this = $(el_this);
    var app = this;
    var postid = $this.parent().parent().data('pos');
    var result = undefined;
    var p_l = '';
    var promise = null;
    if (app.post_links_id !== postid) {
        promise = $.ajax({type: 'POST', data: {'postid': postid}, url: app.urls['post_links_url'], dataType: 'json', async: true});
        promise.done(function(result){
            if ((result) && (result['result'] == 'ok')) {
                var data = result['data'];
                p_l = '<a href="' + data['c_url'] + '">' + data['c_title'] + '</a> | <a href="' + data['f_url'] + '">' + data['f_title'] + '</a><br />';
                //var d_length = data['tags'].length;
                for (var i = 0; i < data['tags'].length; i++) {
                    p_l += '<a href="' + data['tags'][i]['url'] + '">' + data['tags'][i]['tag'] + '</a>, ';
                }
                var offset = $this.offset();
                app.post_links_id = postid;
                app.$post_links.children('.post_links_content').html(p_l);
                app.$post_links.css({'top': offset.top, 'left': offset.left})
                               .show();
            }
            else {
                alert(result['data']);
            }
        });
    }
    else {
        app.$post_links.show();
    }
    return(false);
},
}

$(document).ready(function() {
    if ($('#only_unread_checkbox').length > 0) {
        app.$only_unread_checkbox = $('#only_unread_checkbox');
        app.$only_unread_checkbox.click(function() {
            app.setOnlyUnread(this);
        });
    }
    $(document).ajaxStart(function() { $('#loading').show(); });
    $(document).ajaxStop(function() { $('#loading').hide(); });
    path = window.location.pathname;
    app.$toolbar = $('#global_tools');
    if (path == '/') {
        app.$status_element = $('#status').children('span');
        app.status_interval_handler = setInterval(app.checkStatus, 5000);
        app.checkStatus();
    }
    else if (path == '\/group\/category') {
        app.groupByCategory();
    }
    else if (/\/group\/tag\/.*/.test(path)) {
        var t_out = -1;
        app.$search_field = $('.search_field');
        app.$search_result_window = $('.search_result');
        app.$search_field.on('focus', function() {
            if (app.all_tags == null) {
                app.$search_field.attr('disabled', 'true');
                app.loadAllTags(function(data){
                    app.all_tags = data;
                    app.buildTagsIndex();
                    app.$search_field.removeAttr('disabled');
                });
                app.$search_field.on('keyup', function() {
                    if (!(t_out == -1)) {
                        app.$search_result_window.hide();
                        clearTimeout(t_out);
                    }
                    t_out = setTimeout(function() {
                        app.searchTag();
                        app.showSearchResult();
                    }, 500);
                });
            }
        })
    }
    else if (/^\/feed*/.test(path) || /^\/category*/.test(path) || /^\/tag/.test(path)) {
        app.$post_links = $('#post_links');
        $div_posts = $('div.post');
        app.$current_post = $div_posts.eq(0);//$('.post').eq(0);
        app.$current_post.addClass('current_post');
        app.posts_count = $div_posts.length;
        $('#posts_count').text(app.posts_count);
        $div_posts.click(function() {
            app.setCurrentPost(this);
        });
        var $window= $(window);
        app.scroll_position = $window.scrollTop();
        $window.on('scroll', function() {
            var sc_t = $window.scrollTop();
            if (app.scroll_position >= sc_t) {
                app.scrollUp(sc_t);
            }
            else {
                app.scrollDown(sc_t);
            }
        });
        $div_posts.on('touchstart', function(e){
            touch = e.originalEvent.changedTouches[0];
            app.startX = touch.pageX;
            app.startY = touch.pageY;
        });
        $div_posts.on('touchmove', function(e){
            app.is_gesture = true;

        });
        $div_posts.on('touchend', function(e){
            touch = e.originalEvent.changedTouches[0];
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
        $div_posts.on('touchcancel', function(e){
            touch = e.originalEvent.changedTouches[0];
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
            case 'category':
            case 'tag': {
                app.group_id = $('.page').data('tag');
                break;
            }
        }
        app.current_page = 1;
        app.syncReadAllButton();
        $('a.post_show_links').click(function() {
            app.showPostLinks(this);
        });
        $('.post_links_close').on('click', function(){
            $(this).parent().hide();
        });
        $('#help_button').on('click', function() {
            app.showHelp(this);
        });
        $('span.read_button').on('click', function() {
            app.readOne(this);
        });
        $('#read_all').click(function(){
            app.readAll(this);
        });
        $('a.post_show_content').click(function() {
            var $prnt = $(this).parent();
            app.setCurrentPost($prnt.parent());
            app.showContent($prnt);
            return(false);
        });
        $('.post_title_link').click(function() {
            var self = $(this).parent().parent().find('.read_button');
            if (self.hasClass('unread')) {
                setTimeout(function() {self.click()}, 50);
            }
        });
        $('#show_all').click(function(){
            app.showAll(this);
        });
        app.cloud_items_count = $('li.cloud_item').length;
        if (app.cloud_items_count != 0) {
            $('#cloud_items_count').text(app.cloud_items_count);
        }
        $(document).keydown(function(e) {
            key = e.keyCode || e.charCode;
            switch (key) {
                case 65: {
                    if (e.shiftKey) {//shift-a
                        $('#read_all').click();
                    }
                    break;
                }
                case 83: {
                    if (e.shiftKey) {//shift-s
                        /*$div_posts.each(function() {
                            app.showContent($(this).children('.post_content'));
                        });*/
                        $('#show_all').click();
                    }
                    else {
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
                }
                case 27: {
                    $('#help_window').hide();
                    app.$post_links.hide();
                }
            }
        });
        /*$(document).scroll(function(){ //not async version, need change
            if (!app.all_page_loaded) {

                //app.loadPostsContent();
            }
        });*/
        //$('#show_tags').click(app.showTags);
    }
});

})(jQuery);