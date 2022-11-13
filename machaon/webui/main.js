//
// 共通関数
//
const common_mixin = {
    data: function(){
        return {
            status: 1,
            response: null,
        }
    },
    methods: {
        putLog: function(x){
            console.log(x);
        },
        objectKeys: function(o){
            if(o == null){ return []; }
            return Object.keys(o)
        },
        optional: function(v, def){
            if(v == null) 
                v = (def == null ? "" : def);
            return v;
        },
        ordinalDate: function(ordinal){
            let future = new Date('Jan 1, 0001 0:0:0');
            future.setDate(future.getDate() + ordinal - 1);
            const y = future.getFullYear();
            const m = future.getMonth() + 1;
            const d = future.getDate();
            return y + "/" + m + "/" + d;
        },
        queryServer: function(apiurl, params, modfn, self) {
            // サーバーにGETアクセスを投げる
            if(self == null)
                self = this;
            let url = this.queryServerUrl(apiurl, params);
            let xhr = new XMLHttpRequest();
            xhr.open("GET", url, true);
            xhr.onreadystatechange = function(){
                if(xhr.readyState === XMLHttpRequest.DONE){
                    const status = xhr.status;
                    if (status >= 200 && status < 400) {
                        // リクエストが正常に終了した
                        if(xhr.response){
                            let resp = JSON.parse(xhr.response);
                            if(modfn){
                                const ret = modfn(resp);
                                if(ret === null)
                                    return; // 別のリクエスト送信を開始した
                                resp = ret;
                            }
                            self.response = resp;
                        }else{
                            self.response = {}
                        }
                        self.status = 1;
                    }else{
                        // エラーがおきた
                        self.response = { error: null };
                        self.status = -1;
                        // サーバーに到達出来るか調べる
                        self.reachServer(status);
                    }
                }else if(xhr.readyState == XMLHttpRequest.LOADING){
                    // 読み込み中
                    this.status = 100;
                }
            }
            this.status = 100;
            // リクエスト送信
            xhr.send();
        },
        queryServerUrl: function(apiurl, params){
            let url = App.starturl + apiurl;
            if(params != null && params.length > 0)
                url += "?" + params.join("&");
            return url;
        },
        postServer: function(apiurl, params, data, self) {
            // サーバーにGETアクセスを投げる
            if(self == null)
                self = this;
            let url = this.queryServerUrl(apiurl, params);
            let xhr = new XMLHttpRequest();
            xhr.open("POST", url, true);
            
            let serdata = null;
            if(typeof data === "string"){
                xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded;charset=utf-8');
                serdata = encodeURIComponent(data);
            }else{
                xhr.setRequestHeader('Content-Type', 'application/json');
                serdata = JSON.stringify(data);
            }
            
            xhr.onreadystatechange = function(){
                if(xhr.readyState === XMLHttpRequest.DONE){
                    const status = xhr.status;
                    if (status >= 200 && status < 400) {
                        // リクエストが正常に終了した
                        if(xhr.response){
                            let resp = JSON.parse(xhr.response);
                            self.response = resp;
                        }else{
                            self.response = {}
                        }
                        self.status = 1;
                    }else{
                        // エラーがおきた
                        self.response = { error: null };
                        self.status = -1;
                        // サーバーに到達出来るか調べる
                        self.reachServer(status);
                    }
                }else if(xhr.readyState == XMLHttpRequest.LOADING){
                    // 読み込み中
                    this.status = 100;
                }
            }
            this.status = 100;

            // リクエスト送信
            xhr.send(serdata);
        },
        reachServer: function(errorstatus){
            // サーバーに到達出来るか調べる
            let exhr = new XMLHttpRequest();
            exhr.open("GET", this.queryServerUrl("/v1/hello"), true);
            exhr.onreadystatechange = function(){
                if(exhr.readyState === XMLHttpRequest.DONE){
                    if (exhr.status >= 200 && exhr.status < 400) {
                        this.response = { error: errorstatus }; // 到達できた
                        this.status = -1;
                    }
                }
            }.bind(this);
            exhr.send();
        }
    }
}

//
// 公開するインターフェース
//
var App = {
// 定数
//starturl: "http://192.168.10.201:51000",
starturl: "http://localhost:32100",
vue: {
	el: '#main',
    components: {},
    mixins: [ common_mixin ],
	data: {
        active_component: "empty-window",
        results: [],
	},
    computed: {
        onFilemenu: function(){
            return this.active_component.indexOf("record-") === 0;
        }
    },
    methods: {
        update: function(){
            this.queryServer('/v1/chamber', null, resp => {
                this.results.push.apply(this.results, resp);
                return resp;
            });
        },
        clear: function(){
            this.results = [];
        }
    }
},    
start: function(){
    // エラーハンドラを設定
    Vue.config.errorHandler = function(err, vm, info){
        console.log(`Vue.config.errorHandlerで補足されたエラー: ${info}`, err);
    };
    window.addEventListener("error", function(event){
        console.log("'error' EventListenerで補足されたエラー", event.error);
    });
    window.addEventListener("unhandledrejection", function(event){
        console.log("'unhandledrejection' EventListenerで補足されたエラー", event.reason);
    });
    // アプリ生成
    var app=new Vue(App.vue);
    return app;
},

};

