//
// コンポーネント
//
var components = App.vue.components;

//
function eventEmitter(event, args){
    let eargs = [q(event)];
    if(args)
        eargs.push.apply(eargs, args);
    return qq('$emit(' + eargs.join(", ") + ')')
}
function q(s){ // シングルクォーテーションで囲む
    return "'" + s + "'"
}
function qq(s){ // ダブルクォーテーションで囲む
    return '"' + s + '"'
}

//
//
//
components['async-contents'] = {
    props: ['status', 'response'],
    template: '<div>'
        + '<div v-if="status == 1">'
            + '<slot></slot>'
        + '</div>'
        + '<div v-else-if="status == -1">'
            + '<p v-if="response.error == null">サーバーに到達できません</p>'
            + '<p v-else>サーバーエラーが発生しました。ログを確認してください</p>'
            + '<slot></slot>'
        + '</div>'
        + '<div v-else>'
            + '<p>読み込み中...</p>'
            + '<slot></slot>'
        + '</div>'
        + '</div>'
}

// 初期状態
components['empty-window'] = {
    template: '<div> Ready </div>'
}

// 未実装
components['under-construction'] = {
    template: '<div> 工事中。。。 </div>'
}

//
components['command-input'] = {
    props: [],
    mixins: [ common_mixin ],
    data: function(){
        return {
            extend : false,
            input : "",
            history : []
        }
    },
    methods: {
        extendInput: function(){
            this.extend = !this.extend;
        },
        execute: function(){
            if(!this.input){
                return;
            }
            const cmd = this.input;
            this.postServer("/v1/message/", null, cmd);
            this.$emit("inputted");
            this.input = "";
            this.history.push({
                "value" : cmd
            });
        },
        rollbackInput: function(){
            if(this.history.length === 0)
                return;
            const hi = this.history[this.history.length-1];
            this.input = hi.value;
        }
    },
	template: '<div class="command-input">'
        + '<div>'
            + '<input class="input monospace-text" type="text" v-model="input"'
                + ' @keydown.enter="execute" @keydown.shift.right="rollbackInput"' 
                + ' placeholder="コマンド"></input>'
            + '<input class="optional" type="button" value="拡大" @click="extendInput"></input>'
            + '<input class="send" type="button" value="実行" @click="execute"></input>'
        + '</div>'
    + '</div>'
}

components['result-view'] = {
    props: ["results"],
    methods: {
        tagStyle: function(tag){
            if(tag === "input")
                return "input"
            else if(tag === "error")
                return "errors"
            else if(tag === "warn")
                return "warn"
            else
                return ""
        }
    },
	template: '<div class="result-view monospace-text">'
        + '<div v-for="msg in results">'
            + '<p class="line" v-if="msg.tag!==' + q("progress-display") + '">'
                + '<span class="tagStyle(msg.tag)">{{ msg.value }}</span>'
            + '</p>'
        + '</div>'
    + '</div>'
}
