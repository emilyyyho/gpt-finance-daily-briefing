from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import patch

import collect_news as news
from run_briefing import deliver_edition, due_editions
from send_feishu import DeliveryRejected


class PipelineTests(unittest.TestCase):
    def test_china_time_boundaries(self):
        for hour, expected in ((0,0),(7,0),(8,1),(19,1),(20,2),(23,2)):
            self.assertEqual(len(due_editions(datetime(2026,9,14,hour,tzinfo=news.CST))),expected)

    def test_freshness_requires_publication_not_snapshot_time(self):
        now=datetime(2026,9,14,8,tzinfo=news.CST)
        raw={'updatedTime':int(now.timestamp()*1000),'items':[
            {'title':'today','url':'https://example.com/1','pubDate':int(now.timestamp()*1000)},
            {'title':'old','url':'https://example.com/2','pubDate':int((now-timedelta(days=2)).timestamp()*1000)},
            {'title':'unknown','url':'https://example.com/3'},
            {'title':'future','url':'https://example.com/4','pubDate':int((now+timedelta(hours=1)).timestamp()*1000)},
            {'title':'bad link','url':'javascript:alert(1)','pubDate':int(now.timestamp()*1000)}]}
        with patch.object(news,'fetch',return_value=json.dumps(raw).encode()):
            items,health=news.collect_source(news.SOURCES[0],now)
        self.assertEqual([i['title'] for i in items],['today'])
        self.assertEqual(health['excluded_unknown_time'],1)

    def test_source_outage_is_visible(self):
        with patch.object(news,'fetch',side_effect=TimeoutError()):
            items,health=news.collect_source(news.SOURCES[0],datetime.now(news.CST))
        self.assertEqual(items,[])
        self.assertEqual(health['status'],'error')

    def test_duplicate_titles_merge(self):
        items=[{'title':'共同新闻','url':f'https://example.com/{i}','published_at':f'2026-09-14T08:0{i}:00+08:00'} for i in range(2)]
        self.assertEqual(len(news.deduplicate(items)),1)

    def entry(self):
        return {'parts':[{'text':'part 1','status':'sent'},{'text':'part 2','status':'pending'}]}

    def test_resume_skips_acknowledged_parts_and_saves_intent(self):
        entry=self.entry();saved=[];sent=[]
        deliver_edition(entry,'unused',lambda:saved.append(entry['parts'][1]['status']),lambda *args:sent.append(args[1]))
        self.assertEqual(sent,['part 2']);self.assertEqual(saved[0],'sending');self.assertEqual(entry['status'],'sent')
        deliver_edition(entry,'unused',lambda:None,lambda *args:sent.append(args[1]))
        self.assertEqual(sent,['part 2'])

    def test_no_send_if_durable_intent_cannot_be_saved(self):
        entry=self.entry();sent=[]
        def fail():raise RuntimeError('storage unavailable')
        with self.assertRaises(RuntimeError):deliver_edition(entry,'unused',fail,lambda *args:sent.append(args))
        self.assertEqual(sent,[])

    def test_unknown_delivery_is_not_blindly_retried(self):
        entry=self.entry();calls=[]
        def timeout(*args):calls.append(1);raise TimeoutError()
        deliver_edition(entry,'unused',lambda:None,timeout)
        deliver_edition(entry,'unused',lambda:None,timeout)
        self.assertEqual(len(calls),1);self.assertEqual(entry['status'],'uncertain')

    def test_definite_rejection_has_bounded_retries(self):
        entry=self.entry();calls=[]
        def reject(*args):calls.append(1);raise DeliveryRejected()
        for _ in range(5):deliver_edition(entry,'unused',lambda:None,reject)
        self.assertEqual(len(calls),3);self.assertEqual(entry['status'],'failed')

    def test_crashed_sending_state_needs_review(self):
        entry=self.entry();entry['parts'][1]['status']='sending';calls=[]
        deliver_edition(entry,'unused',lambda:None,lambda *args:calls.append(args))
        self.assertEqual(calls,[]);self.assertEqual(entry['status'],'uncertain')


if __name__=='__main__':unittest.main()
