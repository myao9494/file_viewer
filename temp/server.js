var express = require('express');
var bodyParser = require('body-parser');
var path = require('path');
var Promise = require('bluebird');
require("date-format-lite");

var port = 1337;
var app = express();
var mysql = require('promise-mysql');

var cookieSession = require("cookie-session");
app.set('trust proxy', 1)
app.use(
	cookieSession({
		name: "__session",
		keys: ["key1"],
		maxAge: 24 * 60 * 60 * 100,
		secure: true,
		httpOnly: true,
		sameSite: 'none'
	})
);

// var sqlite3 = require('sqlite3');
// let db_3 = new sqlite3.Database('gantt_howto_node.db', sqlite3.OPEN_READWRITE, (err) => 
// { if (err) { console.error(err.message); } console.log('Connected to the ocs_athlete database.'); }); 

var db = mysql.createPool({
	host: 'localhost',
	user: 'root',
	password: '',
	database: 'gantt_howto_node'
});

var moment = require('moment-timezone');

app.use(express.static(path.join(__dirname, "public")));
app.use(bodyParser.urlencoded({extended: true}));

app.listen(port, function () {
	console.log("Server is running on port " + port + "...");
});

app.get("/data", function (req, res) {
	Promise.all([
		db.query("SELECT * FROM gantt_tasks ORDER BY sortorder ASC"),
		db.query("SELECT * FROM gantt_links")
	]).then(function (results) {
		var tasks = results[0],
			links = results[1];

		for (var i = 0; i < tasks.length; i++) {
			// start_dateをMomentオブジェクトに変換（タイムゾーンの変更なし）
			tasks[i].start_date = moment(tasks[i].start_date);

			// progressが1でない場合は、durationを使ってend_dateを計算
			if (tasks[i].progress != 1) {
				tasks[i].end_date = tasks[i].start_date.clone().add(tasks[i].duration, 'days');
			} else if (tasks[i].end_date) {
				// progressが1で、end_dateが設定されている場合は、そのend_dateを使用
				tasks[i].end_date = moment(tasks[i].end_date);
			} else {
				// progressが1で、end_dateが設定されていない場合は、start_dateと同じにする
				tasks[i].end_date = tasks[i].start_date.clone();
			}

			// start_dateとend_dateをISO 8601形式の文字列に変換
			tasks[i].start_date = tasks[i].start_date.format();
			tasks[i].end_date = tasks[i].end_date.format();

			// durationを数値に変換
			tasks[i].duration = parseInt(tasks[i].duration, 10);
			tasks[i].open = true;

			// console.log(`Task ID: ${tasks[i].id}, Start Date: ${tasks[i].start_date}, Duration: ${tasks[i].duration}, Progress: ${tasks[i].progress}, End Date: ${tasks[i].end_date}`);
		}

		// end_dateの値をログに出力
		// console.log("Tasks with end_date:", tasks.map(task => ({ id: task.id, end_date: task.end_date })));

		res.send({
			data: tasks,
			collections: {links: links}
		});

	}).catch(function (error) {
		sendResponse(res, "error", null, error);
	});
});


// add new task
app.post("/data/task", function (req, res) { // adds new task to database
	var task = getTask(req.body);

	db.query("SELECT MAX(sortorder) AS maxOrder FROM gantt_tasks")
		.then(function (result) { /*!*/ // assign max sort order to new task
			var orderIndex = (result[0].maxOrder || 0) + 1;
			// return db.query("INSERT INTO gantt_tasks(text, start_date, duration, progress, parent, sortorder) VALUES (?,?,?,?,?,?)",
			// 	[task.text, task.start_date, task.duration, task.progress, task.parent, orderIndex]);
			return db.query("INSERT INTO gantt_tasks(text, start_date, duration, progress, parent,kind_task,ToDo,task_schedule,folder,url_adress,mail,memo,hyperlink,color,textColor,owner_id,sortorder,edit_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
			[task.text, task.start_date, task.duration, task.progress, task.parent,task.kind_task,task.ToDo,task.task_schedule,task.folder,task.url_adress,task.mail,task.memo,task.hyperlink,task.color,task.textColor,task.owner_id, orderIndex,task.edit_date]);
		})
		.then(function (result) {
			sendResponse(res, "inserted", result.insertId);
		})
		.catch(function (error) {
			sendResponse(res, "error", null, error);
		});
});

// update task
app.put("/data/task/:id", function (req, res) {
	var sid = req.params.id,
		target = req.body.target,
		task = getTask(req.body);

    var endDate = task.progress == 1 ? formatDateForMySQL(moment().add(1, 'days')) : task.end_date;
    // var endDate = task.progress == 1 ? formatDateForMySQL(moment()) : task.end_date;

	Promise.all([
		db.query("UPDATE gantt_tasks SET text = ?, start_date = ?,end_date = ?, duration = ?, progress = ?, parent = ?, kind_task = ?, ToDo = ?, task_schedule = ? ,folder = ?, url_adress = ?, mail = ?, memo = ?, hyperlink = ?, color = ?, textColor = ?, owner_id = ? , edit_date = ? WHERE id = ?",
			[task.text, task.start_date, endDate ,task.duration, task.progress, task.parent,task.kind_task,task.ToDo,task.task_schedule,task.folder,task.url_adress,task.mail,task.memo,task.hyperlink,task.color,task.textColor,task.owner_id,task.edit_date, sid]),
		updateOrder(sid, target)
	])
		.then(function (result) {
			sendResponse(res, "updated");
		})
		.catch(function (error) {
			sendResponse(res, "error", null, error);
		});
});

function updateOrder(taskId, target) {
	var nextTask = false;
	var targetOrder;

	target = target || "";

	if (target.startsWith("next:")) {
		target = target.substr("next:".length);
		nextTask = true;
	}

	return db.query("SELECT * FROM gantt_tasks WHERE id = ?",
		[target])
		.then(function (result) {
			if (!result[0])
				return Promise.resolve();

			targetOrder = result[0].sortorder;
			if (nextTask)
				targetOrder++;

			return db.query("UPDATE gantt_tasks SET sortorder = sortorder + 1 WHERE sortorder >= ?",
				[targetOrder])
				.then(function (result) {
					return db.query("UPDATE gantt_tasks SET sortorder = ? WHERE id = ?",
						[targetOrder, taskId]);
				});
		});
}

// delete task
app.delete("/data/task/:id", function (req, res) {
	var sid = req.params.id;
	db.query("DELETE FROM gantt_tasks WHERE id = ?", [sid])
		.then(function (result) {
			sendResponse(res, "deleted");
		})
		.catch(function (error) {
			sendResponse(res, "error", null, error);
		});
});

// add link
app.post("/data/link", function (req, res) {
	var link = getLink(req.body);

	db.query("INSERT INTO gantt_links(source, target, type) VALUES (?,?,?)",
		[link.source, link.target, link.type])
		.then(function (result) {
			sendResponse(res, "inserted", result.insertId);
		})
		.catch(function (error) {
			sendResponse(res, "error", null, error);
		});
});

// update link
app.put("/data/link/:id", function (req, res) {
	var sid = req.params.id,
		link = getLink(req.body);

	db.query("UPDATE gantt_links SET source = ?, target = ?, type = ? WHERE id = ?",
		[link.source, link.target, link.type, sid])
		.then(function (result) {
			sendResponse(res, "updated");
		})
		.catch(function (error) {
			sendResponse(res, "error", null, error);
		});
});

// delete link
app.delete("/data/link/:id", function (req, res) {
	var sid = req.params.id;
	db.query("DELETE FROM gantt_links WHERE id = ?",
		[sid])
		.then(function (result) {
			sendResponse(res, "deleted");
		})
		.catch(function (error) {
			sendResponse(res, "error", null, error);
		});
});


function getTask(data) {
    return {
        text: data.text,
        start_date: moment(data.start_date).tz('Asia/Tokyo').format("YYYY-MM-DD"),
        end_date: data.end_date ? moment(data.end_date).tz('Asia/Tokyo').format("YYYY-MM-DD") : null,
        duration: data.duration,
        progress: data.progress || 0,
        parent: data.parent === '' ? null : data.parent,
        kind_task: data.kind_task,
        ToDo: data.ToDo,
        task_schedule: data.task_schedule,
        folder: data.folder,
        url_adress: data.url_adress,
        mail: data.mail,
        memo: data.memo,
        hyperlink: data.hyperlink,
        color: data.color,
        textColor: data.textColor,
        owner_id: data.owner_id === '' ? 0 : data.owner_id, // 空の場合は0を設定
        edit_date: data.edit_date
    };
}

function getLink(data) {
	return {
		source: data.source,
		target: data.target,
		type: data.type
	};
}

function sendResponse(res, action, tid, error) {

	if (action == "error")
		console.log(error);

	var result = {
		action: action
	};
	if (tid !== undefined && tid !== null)
		result.tid = tid;

	res.send(result);
}

// 日付をMySQLの形式に変換する関数を修正
function formatDateForMySQL(date) {
    return moment(date).tz('Asia/Tokyo').format('YYYY-MM-DD HH:mm:ss');
}